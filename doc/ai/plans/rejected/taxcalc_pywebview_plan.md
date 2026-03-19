# Plan: Tax Calculator as PyWebView Desktop App

Replace the ipywidgets GUI in `test/taxcalc.ipynb` with a standalone PyWebView desktop app, reusing patterns and code from the e-ORP desktop implementation where possible.

---

## 1. Current state

**taxcalc.ipynb** (single code cell):

- **Inputs:** Tax year, Net Earnings, IRA Distrib., QCD, Interest, Dividends, SSA income, ST Gains, LT Gains, Gains Carry; plus a text field for the e-ORP test CSV path.
- **Actions:** “Run Tax Calc” (single-year calc from inputs), “Test e-ORP Tax Calc” (loop over CSV rows, compare to `income_tax`).
- **Output:** Text in `out_box` (year, income, LTCG, AGI, total tax, tax on income, tax on cap gains, marginal rates, bracket end). Errors in `err_out`.
- **Logic:** `tax_brackets_for_year()`, `calc_tax()`, `tax_calc()` (dollars → $000s for OORPy), plus inline tax tables (MFJ/Single, 2025/2026).

**e-ORP desktop:** `main.py` (window + `frontend/index.html` + `js_api=Api`), `backend.Api` (params, run_projection in thread, save/load, poll_log), frontend (HTML form, `app.js` bridge, collect/populate params, render plotly/table/heading).

---

## 2. Goals

- Ship a **double-clickable desktop app** for the tax calculator (no Jupyter).
- **Share code** with e-ORP: bridge/Cocoa handling, frontend patterns, path resolution, and (optionally) a thin shared shell.
- Keep **taxcalc.ipynb** runnable by having it call into the same core tax module (no duplicate tax logic).

---

## 3. Shared code opportunities

| Area | e-ORP | Tax Calculator app | Reuse approach |
|------|--------|--------------------|-----------------|
| **App entry** | `main.py`: chdir, `webview.create_window(..., frontend/index.html, js_api)`, `webview.start()` | Same pattern, different title/path/size | Copy/slightly parameterize or add a small shared `desktop_shell.py` that takes (title, html_path, api_class, window_kwargs). |
| **Cocoa bridge** | Inline script in `index.html` fixing `_jsApiCallback` / `stringify` for WebKit | Same WebView engine on macOS | **Share:** Copy the same `<script>` block into taxcalc’s HTML, or serve a shared `bridge-patch.js` from a common frontend fragment. |
| **Path resolution** | `_APP_DIR`, `_resolve_path(filepath)` for relative paths under app dir | Same need for “Test” CSV path and any future save/load | **Share:** Put `_resolve_path()` (and optionally `_APP_DIR`) in a small shared module (e.g. `app_util.py`), import in both backends. |
| **Frontend layout** | Full-width form, grid-2 / grid-4, panels, result area, buttons | Simpler: one form + result text + two buttons | **Share:** Reuse `style.css` patterns (grids, panels, buttons, `.result-section-title`) or a shared `common.css`; taxcalc uses a subset. No Plotly. |
| **JS bridge init** | `pywebviewready`, poll fallback, `getApi()`, status text | Same: wait for API, show “Ready” / “Failed” | **Share:** Same init + status pattern; taxcalc only needs `run_calc`, `run_test`, optional `get_inputs`/`set_inputs`. |
| **Backend API** | `Api`: get/set params, run_projection (thread), save/load params, poll_log | Smaller API: get/set inputs, run_calc (sync), run_test (sync or thread) | **No** shared Api class; **do** share pattern: one class, methods invoked from JS, return serializable data. |

**Recommendation:** Introduce a minimal shared layer: `app_util.py` (path resolution), and optionally `desktop_shell.py` (create window + start webview). Frontend: shared Cocoa script snippet and, if useful, a shared `common.css`; taxcalc gets its own `index.html` and `app.js` that call a small TaxcalcApi.

---

## 4. Extract tax logic into a shared module

- Add **`taxcalc_core.py`** (or a subpackage) at repo root or under `e-ORP/`:
  - Move tax tables (MFJ/Single, 2025/2026) and `tax_brackets_for_year`, `calc_tax` from the notebook into this module.
  - Expose a single entry point used by both UIs, e.g. `tax_calc(year, income_dollars, capgains_dollars, MAGI_dollars, rate_infla=0.02)` returning a dict or tuple (total_tax, mrate, crate, brend, std_deduction, ibtax, cgtax) in consistent units (e.g. $000s for compatibility with e-ORP).
  - Keep “Test e-ORP Tax Calc” logic: function that takes a CSV path (or DataFrame), runs `calc_tax` per row using `tax_brackets_for_year`, compares to `income_tax` column; returns list of `{year, ok, message}` or similar.
- **taxcalc.ipynb:** Replace inline tax code with `from taxcalc_core import tax_calc, run_test_csv` (or equivalent). Keep ipywidgets only for inputs/buttons/output; wire them to the shared functions.
- **Tax calculator desktop app:** Backend imports the same `taxcalc_core` and calls `tax_calc` / test function; no duplicate tax logic.

Optionally, align `taxcalc_core` with e-ORP’s `planner`/`solver` tax conventions later (e.g. same bracket representation) so e-ORP could call into it for consistency.

---

## 5. New desktop app layout

**Directory (choose one):**

- **Option A:** Same repo, sibling to e-ORP frontend: e.g. `e-ORP/taxcalc_app/main_taxcalc.py`, `taxcalc_app/frontend/index.html`, `taxcalc_app/frontend/app.js`, `taxcalc_app/frontend/style.css` (or link to shared `common.css`), `taxcalc_app/backend_taxcalc.py`.
- **Option B:** Dedicated top-level folder: `taxcalc_desktop/` with its own `main.py`, `backend.py`, `frontend/`, and dependency on `e-ORP` (or repo root) for `taxcalc_core` and any shared util.

**Backend (`backend_taxcalc.py` or equivalent):**

- Use `_resolve_path()` from shared `app_util` for the “Test” CSV path.
- **Api class:**  
  - `get_inputs()` → dict of current input values (year, npay, irad, iqcd, …).  
  - `set_inputs(d)` → update from dict (for future load/paste).  
  - `run_calc()` → call `tax_calc(...)` with current inputs; return a **result object** (e.g. dict with keys like `year`, `income`, `agi`, `total_tax`, `tax_income`, `tax_cg`, `mrate`, `crate`, `bracket_end`, `error`) for the frontend to render.  
  - `run_test(csv_path)` → call test function from `taxcalc_core`; return list of `{year, ok, message}` (or one string) for display.
- No threading required for `run_calc` (fast). `run_test` can be sync or run in a thread with a “Running…” state if the CSV is large; if sync, no poll_log needed.

**Frontend:**

- **HTML:** Form with one section “Inputs” (labels + inputs for year, net earnings, IRA, QCD, interest, dividends, SSA, ST gains, LT gains, gains carry), a text input for “Test output at” (CSV path), and two buttons: “Run Tax Calc”, “Test e-ORP Tax Calc”. Include the same Cocoa bridge script as e-ORP. Result area: a single block (e.g. `<pre>` or `<div class="result-section-title">` + `<pre>`) for main output; optional second block for test results. No Plotly.
- **JS:** On load, optional `get_inputs()` and populate form. “Run Tax Calc” → `api.run_calc()` → show returned result in the result area (formatted text or simple HTML). “Test e-ORP Tax Calc” → `api.run_test(efname)` → show test output. Reuse e-ORP’s bridge-ready and status logic; no `renderResults` for plotly/table.
- **CSS:** Reuse e-ORP panel/grid/button styles (or a shared `common.css`) so the app looks consistent; minimal extra rules for the single result block.

---

## 6. Implementation steps (summary)

1. **Shared util:** Add `app_util.py` with `_APP_DIR` and `resolve_path(filepath)`; use it in e-ORP `backend.py` and in the new taxcalc backend.
2. **Tax core:** Add `taxcalc_core.py` with tax tables, `tax_brackets_for_year`, `calc_tax`, `tax_calc`, and the CSV test function; adjust notebook to import from it.
3. **Taxcalc desktop backend:** New backend module that imports `taxcalc_core` and `app_util`, defines Api (get_inputs, set_inputs, run_calc, run_test).
4. **Taxcalc desktop frontend:** New `frontend/` with index.html (Cocoa script, form, result area), app.js (bridge init, run_calc/run_test handlers, result display), and style (shared or copied subset).
5. **Taxcalc desktop entry:** New `main_taxcalc.py` that creates the window and points to taxcalc frontend and Api (reuse or copy e-ORP’s main pattern; optionally use shared `desktop_shell`).
6. **Docs:** Update README or DESKTOP.md (or add TAXCALC_APP.md) with run instructions and dependency (e.g. `pywebview`, `pandas`); note that `make desktop` is for e-ORP; taxcalc can use the same venv.

---

## 7. Optional: shared desktop shell

If you want one shared entry for “any PyWebView app in this repo”:

- **`desktop_shell.py`** (or `run_desktop_app.py`):  
  - Parses a single argument or env var to choose app: `eorp` | `taxcalc`.  
  - Sets `app_dir` (e.g. `e-ORP` or `taxcalc_app`), `os.chdir(app_dir)`.  
  - Imports the right Api and frontend path (e.g. `frontend/index.html` under that app_dir).  
  - Calls `webview.create_window(title, html_path, js_api=Api(), ...)` and `webview.start(debug=...)`.

Then `main.py` (e-ORP) and `main_taxcalc.py` (taxcalc) become thin wrappers that call `desktop_shell.run('eorp')` / `desktop_shell.run('taxcalc')`. This keeps a single place for Cocoa/debug handling and window defaults if desired.

---

## 8. Result

- **taxcalc.ipynb:** Still works; uses ipywidgets for UI but delegates all tax logic to `taxcalc_core`.
- **Tax Calculator desktop app:** Standalone PyWebView app; same tax results; double-clickable when bundled (e.g. py2app) later.
- **e-ORP:** Gains shared path resolution (and optionally shared shell); no change to existing UX.
- **Code sharing:** Path resolution, Cocoa bridge snippet, frontend/CSS/JS patterns; optional shared shell for multiple apps in the same repo.
