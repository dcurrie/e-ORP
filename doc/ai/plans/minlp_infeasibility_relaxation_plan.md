# e-ORP: MINLP infeasibility diagnostics and constraint relaxation

## 1. Overview and goals

When the SCIP MINLP solver reports **infeasibility**, the user currently gets no explanation. When the solve is **slow** (e.g. time limit hit), there is no way to explore relaxing constraints. This plan adds:

1. **Infeasibility diagnostics:** Identify and report a minimal conflicting set of constraints (IIS) so the user can correct inputs or understand the model.
2. **Foundation for relaxation:** Name every constraint and keep a reference to it so we can later support “suggest relaxations” and/or “interactively relax and re-solve.”

Background and references are in the vault research note: `research/e-ORP-MINLP-infeasibility-and-relaxation.md` (SCIP IIS vs MinUC, PySCIPopt gaps, constraint naming, `chgRhs`/`chgLhs`).

**PySCIPopt version:** e-ORP uses **PySCIPopt 6.x** (`pyscipopt>=6,<7`). Phase 2 uses **`model.generateIIS()`** in-process (no subprocess). See doc/ai/plans/notes_pyscipopt6_upgrade.md.

**Implemented (branch `infeasibilty-reporting`):** Constraints are named `eorp_00001`, … via a local `add_cons` wrapper; Roth limit uses `eorp_rothlim_y{y}`. On infeasible, `generateIIS()` runs and names are returned through `oorp` → `render_dd` → desktop (`iis_report` item + SCIP log). Semantic names (plan §3.1) remain optional follow-up.

**Large IIS in the UI:** A true IIS can still list **hundreds** of rows on multi-year models because feasibility is chained year-to-year. The desktop report explains this, shows the first ~45 names by default, puts the rest behind `<details>`, and offers **Copy all names** for grep / `.lp` cross-reference until semantic naming lands.

**Thin semantic names (implemented):** `add_cons(expr, name=None)` in `solver.py`. High-signal constraints use stable names: `eorp_min_residual_final`; `eorp_spend_delta_y{y}`, `eorp_disp_from_disc_y{y}`; `eorp_fix_disp_y{y}` (net_pretax objective); `eorp_init_*_0`; `eorp_e_rmd_y{y}`, `eorp_j_rmd_y{y}`; `eorp_rothconv_*_le_taxd_y{y}`; `eorp_qcd_*_y{y}`; `eorp_disp_balance_y{y}`; `eorp_net_pretax_def_y{y}`; Roth cap disjunction remains `eorp_rothlim_y{y}`. All other rows stay sequential `eorp_NNNNN`.

**IIS opt-in (desktop):** Checkbox **IIS if infeasible** in Optimizer Controls (default **off**). `run_projection(..., run_iis=False)` → `oorp(..., run_iis=...)` → `oorplp(..., run_iis=...)`. When off, infeasible runs skip `generateIIS()` and log one line; the UI shows infeasible status without an IIS list.

**IIS timing:** `iis/time` is set from the same **`tout`** as `limits/time` (seconds). If `tout <= 0`, IIS falls back to 300 s so it is not unbounded. `iis/silent` reduces log noise.

**Desktop UI (Cocoa / pywebview):** While `generateIIS()` runs, the worker may hold the GIL for a long time; the 200 ms `poll_log` bridge calls Python on the **main** thread and can block repaints (beach ball) so the IIS warning appears only after IIS finishes. **Mitigation:** `window.__eorpPauseLogPoll` set in `iis_prepare_cb` (`backend.py`), honored in `startLogPolling` (`frontend/app.js`), cleared in `runFinished` / new run; brief `time.sleep(0.05)` in `solver.py` immediately before IIS so the UI can paint the “Computing IIS…” line.

**Guiding principles:**

- Prefer the **desktop** app as the target for new UI (run in worker; no change to notebook-only flow until we choose to expose it).
- **No change to model logic** beyond adding names and storing constraint objects; solve path and objective stay the same.
- IIS today is obtained via a **workaround** (write problem → run SCIP binary → parse result) until PySCIPopt exposes an IIS API.

---

## 2. Scope and out-of-scope

| In scope | Out of scope (later) |
|----------|----------------------|
| Add unique `name=` to every `addCons()` / `addConsDisjunction()` in `solver.py`. | Full interactive “relax this constraint” UI (list + loosen + re-solve). |
| Store each constraint object in a structure keyed by name (e.g. dict). | MinUC-based “suggest minimal set to relax” (depends on SCIP/PySCIPopt API). |
| On `status == 'infeasible'`: write problem to `.lp` with `genericnames=False`, run SCIP to compute IIS, map constraint names back, and present a short report to the user. | Automatic “suggest relaxations” when solve is slow (time limit). |
| Optional: same `scip` instance kept (or re-read) so we can add “list conflicting constraints” and, in a later phase, “relax one and re-solve” without rebuilding the full model from scratch. | Changes to notebook-only flow (can be added later if desired). |

---

## 3. Constraint naming and storage (Phase 1)

**Owner:** `solver.py`, function `oorplp`.

### 3.1 Naming convention

- One **unique** name per constraint. Suggested pattern: `{category}_{description}_{y}` for year-indexed constraints, and `{category}_{description}` for single constraints.
- Examples (align with existing comments / variable names):
  - `init_e_Roth_0`, `init_e_Taxd_0`, … for initial-value constraints.
  - `obj_disp_income_y1`, `obj_min_residual` for objective-related constraints.
  - `calc_e_RMD_y1`, `calc_j_RMD_y1`, `calc_afterTax_y1`, … for calculation constraints.
  - `Roth_conv_limit_y1`, `QCD_sum_y1`, `QCD_limit_y1`, `IRMAA_bin0_ge_bin1_y1`, `tax_taxable_income_y1`, `account_e_Roth_y1`, `account_net_pretax_y1`, etc.
- Disjunctions: e.g. `Roth_conv_disj_y1`. Each `addConsDisjunction` is one named constraint.

### 3.2 Storage

- Introduce a **dict** (e.g. `cons_by_name: dict[str, constraint object]`) built as constraints are added.
- For every `scip.addCons(...)` and `scip.addConsDisjunction(...)`, pass `name=...` and assign the return value: `cons_by_name[name] = scip.addCons(..., name=name)`.
- Pass `cons_by_name` out of the model-building block so it can be used later (e.g. for IIS mapping or, in a future phase, for `chgRhs`/`chgLhs`). This may require returning it from `oorplp` or storing it in a structure that the caller can pass to a “report IIS” or “relax” helper.

### 3.3 Exit criterion (Phase 1)

- All constraints in `oorplp` have a unique `name=` and are stored in `cons_by_name`.
- `scip.writeProblem(..., genericnames=False)` produces an `.lp` file whose constraint names match our names (spot-check one run).

---

## 4. Infeasibility diagnostics (Phase 2)

**Trigger:** `scip.getStatus() == 'infeasible'` after `scip.optimize()`.

### 4.1 Flow

1. **Write problem:** Before or after optimize, if we don’t already have a written file, call `scip.writeProblem(filename=..., trans=False, genericnames=False)` so constraint names in the file match `cons_by_name`.
2. **Run SCIP to compute IIS:** Invoke the SCIP binary (subprocess or shell) with:
   - `read <path_to_lp>`
   - `iis`
   - `write iis <path_to_iis_file>` (or equivalent; see SCIP docs).
3. **Parse IIS output:** From the written IIS instance or SCIP’s display, obtain the list of constraint names (and optionally variable bounds) that appear in the IIS.
4. **Map to user-facing text:** Using `cons_by_name` and/or a small map from constraint name → short description (e.g. “Minimum residual (year N)”, “Roth conversion limit (year N)”), produce a short list of “Conflicting constraints: …”.
5. **Present to user:** In the desktop app, show this list in the same place or channel where optimization status is shown (e.g. where “Optimization failed, status infeasible” appears). Optionally also print to the redirected stdout so it appears in the run log.

### 4.2 Implementation details

- **Where to write:** Use a temporary directory or a fixed subdir (e.g. `data/` or a `tmp/` under the repo). Avoid leaving stale `.lp`/IIS files in the user’s working directory; prefer temp files with cleanup, or a single “last infeasible” file that gets overwritten.
- **SCIP binary:** Assume `scip` is on the PATH (same SCIP as used by PySCIPopt) or allow a configurable path. Document in README or doc/ai if needed.
- **Failure to compute IIS:** If the subprocess fails or times out, fall back to a generic message (“Problem is infeasible; could not compute conflicting constraints. Check inputs and constraints.”) and still show status infeasible.

### 4.3 Exit criterion (Phase 2)

- For an intentionally infeasible test case (e.g. contradictory constraints in a small scenario), the desktop run shows “infeasible” and a non-empty list of conflicting constraint names (or short descriptions).
- For a feasible run, no IIS step is run; behavior unchanged.

---

## 5. Optional / future phases (not committed in this plan)

- **Interactive relaxation:** UI that lists constraints (from `cons_by_name` or a filtered set), lets the user select one or more to “relax” (e.g. loosen RHS or drop), then re-solve. Requires keeping the model (or re-reading the written problem) and calling `cons.chgRhs()` / `cons.chgLhs()` or deleting the constraint, then `scip.optimize()` again.
- **Suggest relaxations when slow:** On time limit or gaplimit, optionally run MinUC (if/when available in PySCIPopt) or a heuristic to suggest “relax these constraints to get feasibility.”
- **Notebook:** Same diagnostics can be exposed in the notebook (e.g. print or display the conflicting-constraint list) once the solver side is implemented.

---

## 6. Files to touch

| File | Changes |
|------|--------|
| `solver.py` | Add `cons_by_name`; add `name=` and storage for every `addCons` and `addConsDisjunction`; on infeasible, call write + IIS subprocess + parse + return or pass list of conflicting names/descriptions; optional helper `compute_iis_report(scip, cons_by_name, ...)`. |
| Desktop frontend / backend | Consume the new “conflicting constraints” list and display it where status is shown (e.g. in the same message area or a small expandable section). |
| doc/ai (or README) | Short note that IIS diagnostics require SCIP on PATH (or configurable) and that constraint names are used for reporting. |

---

## 7. Testing

- **Unit / ad hoc:** Construct a small scenario that is infeasible (e.g. two constraints that cannot hold simultaneously). Run `oorplp`; assert status is infeasible and that the reported conflicting set is non-empty and contains at least one of the known conflicting constraints.
- **Regression:** Run an existing feasible scenario; assert status unchanged and that no IIS step alters the returned `dd` or status.
- Prefer tests under `testing/` or a small script that can be run from the repo root with the desktop stack (or solver only) as in existing practice.

---

## 8. Order of work

1. **Phase 1:** Naming and storage in `solver.py` (no UI change). Validate with `writeProblem` and spot-check names.
2. **Phase 2:** Implement write → SCIP IIS → parse → list; return or pass list from `oorplp`/backend to desktop UI; show “Conflicting constraints: …” when infeasible.
3. **Cleanup:** Temp file policy, docs, and any README note about SCIP binary.

End of plan.
