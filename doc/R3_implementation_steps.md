# R3 Plan: Concrete Implementation Steps and Test Strategy

This document gives concrete steps to implement the PyWebView conversion (R3 plan) on a new git branch, and recommends improvements to test coverage so it is standalone and validates the refactor.

---

## Part 1: Git branch and first steps

All commands assume you are in the **e-ORP repository root** (`e-ORP/`, where `.git` lives).

### 1.1 Create the feature branch

```bash
cd /path/to/e-ORP
git status          # ensure clean or committed
git checkout -b pywebview-r3
```

### 1.2 Export the notebook code for extraction

The R3 plan refers to "lines 22–1401", "1404–2580", etc. Those are line numbers within the **single code cell** of `e-ORP.ipynb`, not the JSON file. To work with them:

- **Option A:** Export the notebook to a single `.py` file once, then use that for cuts:
  ```bash
  jupyter nbconvert --to script e-ORP.ipynb --output e-ORP-export
  ```
  Then `e-ORP-export.py` has one line of code per line number in the plan. You can add `e-ORP-export.py` to `.gitignore` and use it only for copy/paste.

- **Option B:** Work directly from the notebook JSON: copy the `source` array of the code cell into a temporary file and join lines, then use the plan’s line ranges to extract blocks.

Recommendation: use Option A so you have a single file where "line 438" is unambiguous.

---

## Part 2: Concrete implementation steps (by stage)

### Stage 1 — Extract and test core logic

| Step | Action | Notes |
|------|--------|--------|
| 1.1 | Create `e-ORP-export.py` from the notebook (see above). | One-time; add to `.gitignore`. |
| 1.2 | Create `planner.py`: copy from export lines 22–1401. | Apply R3 §4.1: `_here` and `__file__` for `historical/rates.csv`, `make_planning_datadict(p, test_mode=..., historical_year_for_rates=..., warn_cb=...)`, all `xxx_box.value` → `p['xxx']`, inject `display_warning` via `warn_cb`, add `PARAM_DEFAULTS` from R3 §4.1 (corrected defaults). Move `squirrel_map`, `set_nut`, `get_nut` into `planner.py` if not already there. |
| 1.3 | Create `solver.py`: copy from export lines 1404–2580. | Apply R3 §4.2: imports from `planner`; add `p` and `warn_cb` to `oorp`, `walk_lap`, `walk`, `three_peat`; replace `hist_box.value` with `p['hist']`; remove all `with out_box:` / `with drb_out:` / `err_out.clear_output()`; add return values `(dd, status, ...)`, `(worst_di_dd, ...)`, `(rf, sm, fname)`; inject `warn_cb` into `oorplp`. |
| 1.4 | Add `test_planner.py` (or `test/test_planner.py`). | Build `params_dict` from `PARAM_DEFAULTS`, call `make_planning_datadict(p, warn_cb=...)`, assert `dd` has expected keys and shape (e.g. `dd['year']`, length). Optionally run `oorplp` with a short timeout and assert status in `['optimal','timelimit','gaplimit']`. |
| 1.5 | Run solver output through existing CSV tests. | Run one projection that writes `data/_explore.csv` using the **new** `solver.py` + `planner.py` (e.g. from a small script that calls `oorp(p, ...)` with default `p`). Then run the **existing** dd_test_revised logic against that CSV (see Part 3 for making this scriptable). |

**Exit criterion:** `python test_planner.py` passes; solver produces CSV that passes the same checks as dd_test_revised (single-run tests).

---

### Stage 2 — Create renderer

| Step | Action | Notes |
|------|--------|--------|
| 2.1 | Create `renderer.py`. | Add `import json`. Copy `display_dd` logic from export (lines 2022–2186) into `render_dd`; replace every `display(...)` with `items.append(...)` and for Plotly use `items.append({'type':'plotly', 'json': json.loads(fig.to_json())})`. Set `pd.options.display.max_columns` / `precision` at module level. |
| 2.2 | Add `render_three_peat(rf, sm)`. | Return list of `{'type':'heading'|'table', ...}` per R3 §4.3. |
| 2.3 | Sanity-check Plotly round-trip. | In a small script or test: build a minimal `dd`, call `render_dd(dd)`, assert first plotly item has `item['json']['data']` and `item['json']['layout']` (dict, not str). Optionally load Plotly in a headless JS env or just assert structure. |

**Exit criterion:** `render_dd(dd)` and `render_three_peat(rf, sm)` return correctly typed items; Plotly item is a dict with `.data`/`.layout`.

---

### Stage 3 — Minimal PyWebView app

| Step | Action | Notes |
|------|--------|--------|
| 3.1 | Add `pywebview>=5.3` to `requirements.txt`. | Do not remove Jupyter deps yet if you want the notebook to keep working in the same branch. |
| 3.2 | Create `backend.py`. | Implement `Api` per R3 §6: `get_params`, `set_params`, `save_params`, `load_params`, `get_params_csv`, `load_params_from_csv`, `get_hist_options`, `_coerce_one`/`_coerce_types`, `run_projection`, `_run_worker` (if/elif/elif/else), `poll_log`, `_QueueWriter`. |
| 3.3 | Create `main.py`. | Per R3 §4.5: absolute `html_path` via `__file__`, `api.window = window` before `webview.start()`. |
| 3.4 | Bundle Plotly JS. | Run the R3 §3 command to locate `plotly/package_data/plotly.min.js`, copy to `frontend/plotly.min.js`. |
| 3.5 | Create `frontend/index.html` and `frontend/app.js` (minimal). | Shell with `#inputs-panel`, `#controls-panel`, `#warnings-panel`, `#scip-log-panel`, `#results-panel`; `pywebviewready` → `get_hist_options`, `get_params`, `populateForm`, `startLogPolling`; Run button → `set_params(collectParams())`, `run_projection(...)`; `renderResults` stub that logs to console; `runFinished` re-enables button. |
| 3.6 | Run and verify. | `python main.py` from repo root; click Run with defaults; confirm no freeze, log text appears, `renderResults` receives data; button re-enables. |

**Exit criterion:** Window opens; Run runs solver in background; log panel updates; results callback fires; button re-enables on success and on exception.

---

### Stage 4 — Full form and results UI

| Step | Action | Notes |
|------|--------|--------|
| 4.1 | Build full form in `index.html`. | All sections from R3 §7.2; every input has `data-param="key"` matching `PARAM_DEFAULTS`; ids for `nlpomode`, `testmode`, `tout`, `glim`, `efname`, `pfname`, `param-buf`, save/load/copy/paste/run buttons. |
| 4.2 | Populate `hist` in `pywebviewready` from `get_hist_options()`. | Per R3 §7.2 code. |
| 4.3 | Add `style.css`. | Grid layout, section borders, table/chart spacing. |
| 4.4 | Complete `app.js`. | `collectParams`/`populateForm` with coercion; full `renderResults` (Plotly `item.json.data`/`.layout`, tables, headings); `appendWarning` with `textContent`; glide `change` → `updateGlidePath`; save/load/copy/paste handlers. |
| 4.5 | Verify. | All 89 params present; save/load file and clipboard; all 9 charts and tables render; warnings display. |

**Exit criterion:** As in R3 Stage 4.

---

### Stage 5 — Polish and requirements

| Step | Action | Notes |
|------|--------|--------|
| 5.1 | Update `requirements.txt` for desktop app. | Remove Jupyter/ipywidgets/ipykernel/etc.; keep pandas, plotly, pyscipopt; add pywebview. (Keep a separate `requirements-notebook.txt` or document notebook venv if you want both.) |
| 5.2 | Fresh venv test. | `python -m venv .venv && pip install -r requirements.txt && python main.py`. |
| 5.3 | Cross-check notebook vs desktop. | Same params file: run notebook (old code path) and desktop app; compare key outputs (e.g. `data/explore.csv` vs desktop-rendered data or exported CSV). |
| 5.4 | Launch from another directory. | `cd /tmp && python /path/to/e-ORP/main.py`; confirm frontend and `historical/rates.csv` load. |

**Exit criterion:** As in R3 Stage 5.

---

## Part 3: Test coverage — improving on dd_test_revised.ipynb

### What dd_test_revised.ipynb does today

- **Input:** Path to CSV(s): e.g. `../data/_explore.csv`, and for 3-peat `_explore.99.csv`, `_explore.1.csv` … `_explore.10.csv`.
- **Logic:** Pure validation: reads CSVs and checks cash-flow identities, QCD constraints, account balance recurrences, bracket scaling, etc. It does **not** run the solver or import e-ORP.
- **Gap:** You must run the main app (notebook or future desktop) first to generate those files; the test is UI-driven (buttons) and not CI-friendly.

### Recommendations to make tests standalone and cover the R3 changes

1. **Extract the validation logic into a Python module**
   - Create `test/validate_dd.py` (or `test/dd_validation.py`) containing:
     - The same `chk_re`, `chk_ae`, `chk_le`, etc.
     - A function `validate_single_run(csv_path)` that reads the CSV and runs the same checks as `test(_)` in the notebook (single-run / oorp).
     - A function `validate_three_peat(base_path)` that, given the base path (e.g. `../data/_explore`), reads `base_path + ".99.csv"` and `base_path + ".1.csv"` … `base_path + ".10.csv"` and runs the same checks as `tes3(_)`.
   - **Benefit:** Any runner (notebook, pytest, or a small script) can call these with a path; no widgets required.

2. **Add a small script or pytest that runs the solver then validates**
   - **Option A — Script:** e.g. `test/run_and_validate.py`:
     - Imports `planner.PARAM_DEFAULTS`, `planner.make_planning_datadict`, `solver.oorp` (and optionally `solver.three_peat`).
     - Builds `p = dict(PARAM_DEFAULTS)`, optionally overrides (e.g. short horizon for speed).
     - Calls `oorp(p, mode=0, objt=0, test='', tout=30, glim=0.02, fname='data/_explore.csv', warn_cb=...)`, then calls `validate_single_run('data/_explore.csv')` and exits 0 only if all checks pass.
     - For 3-peat: call `three_peat(p, ...)` with a path that produces `_explore.99.csv` and `_explore.i.csv`, then call `validate_three_peat('data/_explore')`.
   - **Option B — Pytest:** Same idea: a test that (a) runs `oorp`/`three_peat` with a fixed param set and output path, (b) calls the validation functions, (c) asserts no failures. Use a small timeout (e.g. 60s) and maybe a reduced horizon so CI stays fast.
   - **Benefit:** Single command (e.g. `python test/run_and_validate.py` or `pytest test/test_solver_output.py`) verifies that the **extracted** solver + planner produce output that still satisfies the existing financial/accounting checks. No need to open the notebook.

3. **Keep dd_test_revised.ipynb as a manual/exploratory front end**
   - After extraction, the notebook can be simplified to: import the validation module and the same harness (e.g. `begin_test`, `report_sub`), and on button click read `efname.value` and call `validate_single_run(efname.value)` or `validate_three_peat(...)`, then display results in `out_box`. That keeps the notebook useful for ad-hoc paths and 3-peat file sets without duplicating the check logic.

4. **Add targeted unit tests for the refactor**
   - **planner:** `make_planning_datadict(p, test_mode='', warn_cb=None)` with minimal `p`: assert returned `dd` has expected keys and that `warn_cb` is called when appropriate (e.g. invalid or edge inputs if any).
   - **Parameter bridge:** `load_params` / `load_params_from_csv` with a known CSV string; assert `params` dict matches expected and that types (int/float/str) match `_coerce_*`.
   - **Renderer:** `render_dd(dd, fname)` with a minimal `dd` (e.g. 2–3 years): assert list of items, first plotly item has `json` as dict with `data` and `layout`; assert table items have `html` string.
   - **Backend (optional):** Mock `window.evaluate_js` and run `_run_worker` with a tiny timeout; assert no exception and that `runFinished` is invoked (e.g. via mock call count).

5. **CI**
   - Add a job (e.g. GitHub Actions) that: creates venv, installs requirements, runs `test_planner.py` and the “run solver + validate” test (and any pytest for planner/renderer/params). Optionally run the full notebook with `jupyter nbconvert --execute` and a small timeout if you keep the notebook as a second consumer of the validation module.

---

## Part 4: Suggested file layout after implementation

```
e-ORP/
├── main.py
├── backend.py
├── solver.py
├── planner.py
├── renderer.py
├── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── plotly.min.js
├── historical/
│   └── rates.csv
├── params/
├── data/
├── test/
│   ├── validate_dd.py          # extracted validation logic
│   ├── run_and_validate.py     # run solver + validate (script)
│   ├── test_planner.py         # planner/solver unit tests
│   ├── dd_test_revised.ipynb   # optional: UI over validate_dd
│   └── (optional) test_renderer.py, test_params.py
├── e-ORP.ipynb
└── doc/
    └── R3_implementation_steps.md  # this file
```

---

## Summary

- **Branch:** Create `pywebview-r3`, work off the exported notebook code for clean line-number extraction.
- **Stages 1–5:** Follow the tables above; each stage has a clear exit criterion from the R3 plan.
- **Tests:** Extract dd_test_revised’s checks into `validate_dd.py`; add a script or pytest that runs the solver then runs those validators so tests are standalone and CI-friendly; add small unit tests for planner, params, and renderer; keep the notebook as an optional UI over the same validation logic.
