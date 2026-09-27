# e-ORP: elastic infeasibility diagnostics

Supersedes `minlp_infeasibility_relaxation_plan.md`.

## 1. Why

When the MINLP is infeasible the user needs to know **which dial to turn, and by how
much**, in dollars. The previous attempt (SCIP IIS, branch `infeasibilty-reporting`,
`32895ab`) could not deliver that:

- A true IIS on this model lists **hundreds** of constraints, because feasibility is
  chained year to year. The UI grew a 45-name preview, a `<details>` overflow and a
  "Copy all names" button around output nobody can act on.
- `_iis_constraint_names_from_model` collected `getConss()` only, so **variable bounds
  never appeared in the IIS** — and the hand-tuned bounds in `oorplp` are a confirmed
  source of *spurious* infeasibility (see §5).
- In-process `generateIIS()` holds the GIL, freezing the Cocoa main thread. That forced
  `window.__eorpPauseLogPoll`, `clearWarningsAndScipLogForIIS()` and a `time.sleep(0.05)`
  in the solver.
- The plan's own §7 exit criterion — a test that provokes a real infeasibility — was
  never met.

e-ORP is an **interactive** tool, so time-to-useful-answer dominates. And because return
and inflation projections are uncertain, chasing small optimality gains is unwarranted;
the goal is identifying the key levers.

## 2. Measurements

`ORPy-venv/bin/python`, pyscipopt 6.1.0, mode 0:

| Case | Result |
|---|---|
| `params/infeasible.csv` main solve | `infeasible` in 0.11 s, cut off at the root node |
| Feasibility frontier (bisected) | max attainable nominal residual ≈ 2432.6 vs required 5120.66 |
| Correct diagnosis | residual target ≈ $1,575k (base-year) too high; 3000 → ≈1425 |
| Relaxed re-solve, mode 0 | ≈ 0.1 s |
| `default.csv` with `chty=600` | infeasible **purely** because `nQCD` was capped at `220·infl` |

The diagnostic is essentially free. The IIS machinery was expensive for a worse answer.

## 3. Mechanism

`oorplp` gains `elastic=False, bounds_scale=1.0`. A local `slk()` helper beside
`add_cons` returns a non-negative slack variable in elastic mode and the literal `0.0`
otherwise; since `expr + 0.0` is a no-op in PySCIPopt, **the non-elastic model is
unchanged**. One model builder, so there is nothing to drift between — `e-ORP.ipynb` is
a standing demonstration of what duplicated model code costs this project.

### Slacked constraints (one-sided, shortfall only)

| Constraint | Dial it maps to |
|---|---|
| `eorp_min_residual_final` | the `ftab` input |
| `eorp_disp_from_disc_y{y}` | essential-spending floor (`va0x`/`pr0x`) |
| `eorp_fix_disp_y{y}` | the pinned spending curve in testmode 2 (`incn`/`spndm`/`infs`) |

**Not** slacked, deliberately: cash-flow and definitional identities
(`eorp_disp_balance_y{y}`, `eorp_net_pretax_def_y{y}`); IRS law (RMD divisors, the
statutory QCD limit `108.0·(1+infl)^n·QCD_pax`, QCD-must-come-from-an-RMD); accounting
facts (`eorp_rothconv_*_le_taxd`, `eorp_init_*_0`); the Roth-cap disjunction
(`eorp_rothlim_y{y}` — no meaningful continuous relaxation, handled by a structural
probe); and every unnamed `eorp_NNNNN`.

### Two independent probes

Rather than weighting spending against legacy with an invented exchange rate, ask the
two questions separately:

- **Probe A** — how far must `ftab` drop, holding the spending curve?
- **Probe B** — how far must spending drop, holding `ftab`?

Each ≈0.1 s at mode 0. Slacks are deflated to base-year dollars by `(1+inflation)**-y`
so cross-year magnitudes are comparable and the reported figure is actionable.

In elastic mode the objective is **replaced**, not penalized:
`maximize 1e-6*tie − Σ w·s`. Replacing avoids tuning a big-M against a model that
already needs two numeric fudges to converge. The `1e-6` tie-break makes secondary
reported numbers well-defined and perturbs the slack sum by at most ~$4.

## 4. Probe ordering

```
0. main solve                                  -> infeasible
0a. user mode 1 or 4? mode-0 solve feasible?   -> kind='mode'          STOP
1. probe_bounds (scale 4, mode 0) feasible?    -> kind='bounds'        STOP
2. probe A + probe B (scale 1, mode 0)
   2a. any slack > tol                         -> kind='elastic'       STOP
   2b. all slacks ~0  => cause is structural   -> 3
   2c. infeasible even with slacks             -> 3
3. Roth_conv_max != 'unlimited'? re-solve unlimited -> kind='structural' STOP
4. otherwise                                   -> kind='inconclusive'
```

The bounds probe runs **first** for two reasons: mis-attributing a modeling artifact to
the user's plan is this feature's worst failure mode, and running it first lets the
elastic probes run at `bounds_scale=1.0`, so a suggested `ftab` is achievable in the
model the user will actually re-run.

Step 0a exists because probes run at mode 0, which is not a relaxation of every mode:
it drops basis averaging (looser than modes 1 and 4) but forbids capital losses (tighter
than modes 2 and 4). Without it, a plan failing only under mode 1 or 4 would pass the
4x bounds probe and be reported as an e-ORP bug. Mode 2 needs no baseline -- mode 0 is
strictly tighter than it -- and mode 3 is the same model as mode 0.

Branch 2b is load-bearing: all-slacks-zero means the cause is in none of the user's
dials. **Never return `diagnosis=None` on an infeasible status.**

## 5. Variable bounds

The caps in `oorplp` are modeling artifacts, not user inputs. `bounds_scale` multiplies
`max_tab`/`max_xfr`/`max_inc`/`max_tax` and the remaining literals, **excluding**
`fm_aTax_frac <= 1.0` (a fraction), the `afterTax` lower bound, and the `nQCD` cap
(derived from the charity input). The `to_aTax_unrlz` lower bound *does* scale.

`max_tab` itself is now sized from `planner.asset_ceiling(dd)` rather than a flat
multiple of the starting balance -- see the results section for why that mattered.

**Fixed bug:** `nQCD` — the *non*-QCD portion of charitable giving — was capped at
`220.0*infl` while `QCD + nQCD == charity`. No statute limits ordinary charitable
giving, so any plan with charity above roughly $440k/yr was infeasible for no real
reason. Now bounded by `dd['charity'][y]`. The statutory QCD *constraint* is untouched.

## 6. Cost control

`DIAG_TOUT = max(5.0, min(tout, 20.0))` per probe; `DIAG_GLIM = 5.0` (5% gap). Probes
always run at **mode 0** — modes 1/2/4 add the products and complementarity that make
the model slow, and the difference between modes is at most ~$1.1k/yr of tax, far inside
projection noise. Caveat: mode 0 also sets `no_capital_losses`, which *restricts*, so it
is not a pure relaxation; if every probe is infeasible at mode 0 and the user's mode is
not 0, retry once at their mode. (Not implemented: such a plan currently gets
`kind='inconclusive'`.) Every report carries a "ran in simplified mode" note.

## 7. Reporting

`renderer.render_diagnosis(diag)` replaces `render_dd` on infeasible runs — which also
stops emitting ~15 charts of zeros and a meaningless all-zero CSV, since `oorplp` fudges
`dd` to zeros when infeasible. The table is built with `pandas.to_html(classes=
'orp-table')` like the rest of `renderer.py`, so the frontend needs only the existing
`heading` and `table` item types plus a small `note` type. The same dict is also printed
in `oorp` so it reaches the SCIP log for copy-paste.

## 8. Both front ends

Originally desktop-only, because `e-ORP.ipynb` carried its own copy of the model. That
duplication has since been removed (`notebook_import_shared_modules.md`): the notebook
imports `planner` / `solver` / `renderer` and gets the diagnostics, the triage and the
bound fixes for free, as will anything added later.

`renderer.display_items()` draws the same item list in Jupyter that `app.js` draws in
the desktop webview, so a new result type needs handling in exactly two small places.

## 9. Results (2026-09-26)

Implemented on branch `elastic-infeasibility-diagnostics`. All of the below is measured,
not projected; raw data in `data/_bench_*.csv`.

### Gap limit: the shipped default is now 0.25

23 modern-format scenarios from both clones, mode 0, `tout=60`:

| gap limit | total wall | worst ΔDI vs proven optimum | timeouts |
|---|---|---|---|
| 0 (prove optimality) | 494.6 s | — | 8 |
| **0.25** | **18.8 s** | **−0.199 %** | 0 |
| 0.5 | 16.1 s | −0.444 % | 0 |
| 1.0 | 15.5 s | −0.814 % | 0 |

0.25 captures essentially all of the available speedup — **26x** — for at most a fifth
of one percent of objective, which is far inside the noise of any return or inflation
forecast. Going to 0.5 saves a further 2.7 s across the whole corpus and quadruples the
worst-case loss; not a good trade. `frontend/index.html` now ships `glim` at `0.25`.
Timeout stays at 60 s: mode 0 never needs more than 5.6 s once the gap limit is nonzero,
but the nuanced modes genuinely do.

Reproduce with:

```
./ORPy-venv/bin/python scripts/bench_sweep.py --quick \
    --params-dir params --params-dir /Volumes/evo2Te/dev/e-ORP/params
```

### The diagnostic reproduces the hand-measured frontier

`params/infeasible.csv`: the elastic probe reports the residual target is **$1,575.7k**
(base-year) too high. An independent bisection of SCIP's true feasibility frontier put
it at $1,574.9k. The whole diagnosis runs in well under a second.

### Fixed, found by the bounds probe: `max_tab` ignored the planning horizon

`max_tab` was `min(18316.2, 2 * bas_tab)` -- a flat multiple of the *starting* balance,
applied per year as `max_tab * infl`. So the cap grew at the rate of **inflation** while
the balances it bounds grow at the rate of **return**. Over a long horizon the cap falls
behind and the model goes infeasible with nothing wrong with the plan.

**`params/example_p.csv` -- a shipped example scenario -- was infeasible for exactly
this reason.** 27 years at 7%: the solution needed 3280 against a cap of 1707. The
bounds sweep flagged it as the only infeasible->feasible flip in the corpus, and the
probe named the binding caps (`afterTax`, `net_pretax`).

The old 18316.2 "the 1%" ceiling had the same defect in the other direction: any
portfolio above $18.3M got a cap *below its own opening balance*.

**Fix:** `planner.asset_ceiling(dd)` computes a rigorous per-year ceiling on total
assets -- balances compound no faster than the best sleeve return, only external income
adds, and spending/tax/IRMAA only subtract -- so it bounds every individual account too.
`max_tab` is the largest constant that ceiling demands in this code's `max_tab * infl`
shape, and is taken as `max(2 * bas_tab, needed, ftab)` so it can only ever loosen the
bounds relative to before. `triage_feasibility()` shares the same growth arithmetic.

Measured effect across 20 scenarios, comparing at `glim=0` so gap noise does not
confound it:

| | before | after |
|---|---|---|
| `example_p.csv` | infeasible | **optimal**, DI 28.356 |
| `_test_aa1.csv` DI | 79.883 | **80.220 (+0.422%)** -- the cap had been silently clipping the optimum |
| every other scenario | — | identical to 3 decimal places |
| `_2024_6/7/8/9` | timelimit | **optimal** |
| total wall at glim=0 | 494.6 s | **266.7 s** |
| total wall at glim=0.25 | 18.8 s | 19.2 s |

So it costs nothing at the shipped gap limit, and at a zero gap it is markedly faster
because four more scenarios become provable inside 60 s. The +0.422% on `_test_aa1` is
larger than the entire gap-limit trade-off, and had been invisible.

### Still outstanding: `max_xfr` is not a rigorous bound

`max_xfr = max_tab / 6`, commented as "the max RMD at age 101", also bounds *voluntary*
transfers (`from_aTax`, `to_aTax`, `from_eTaxd`, ...). A voluntary withdrawal can be the
whole account, so one sixth is a heuristic, not a bound, and it can clip the optimum
without any sign that it did. `test_bounds_probe_names_culprits` shows it still binding
on `example_p.csv`, and `_test_aa1.csv` gains a further ~0.04% when the caps are doubled
again. Not fixed here: it is a separate bound with a separate rationale, and unlike
`max_tab` there is no rigorous replacement that is also tight.

### Also found: no-incumbent runs returned garbage

When a time or gap limit stopped the solver before any incumbent was found, `oorplp`
still ran the extraction block and returned whatever `getVal()` happened to hold —
`net_pretax` values of `0.0` and `4.99e96` were observed — and `oorp` printed it as a
successful `FTAB:` line while `render_dd` charted it. `SolveResult.has_solution`
(from `scip.getNSols()`) now gates this, and `SolveResult.ok()` is what callers test.

### Triage calibration

The optimistic ceiling is loose by roughly 1.3–2.2x because it ignores all tax. Across
the 23 modern scenarios, every feasible plan sits at 2.83x headroom or better while
`infeasible.csv` sits at 1.74x, so the advisory threshold is set at 2.0x. Zero hard
warnings fire on the corpus; the advisory fires on exactly one scenario, the one SCIP
proves infeasible.
