# e-ORP: Conversion Plan — Jupyter/ipywidgets → PyWebView

## 1. Overview and guiding principles

The conversion replaces the Jupyter kernel + ipywidgets rendering layer with a
PyWebView native window containing a local HTML/CSS/JS frontend that communicates
with a Python backend over PyWebView's JS↔Python bridge. Everything else —
`make_planning_datadict`, `oorplp`, `oorp`, `three_peat`, `walk`, `display_dd`,
all tax/IRMAA/RMD tables, `historical/rates.csv` loading — is preserved verbatim.
No model logic changes hands.

**Key design decisions driven by the source code:**

- The solver (`oorplp`) is synchronous and can run for tens of seconds or more.
  It **must** run in a worker thread; the PyWebView window runs on the main thread
  and will deadlock if the bridge call blocks it.
- SCIP prints progress text to stdout. The current code captures this with
  `widgets.Output` context managers (`with drb_out:`). The replacement redirects
  `sys.stdout` to a queue that the frontend polls.
- `display_dd` currently calls `display(px.bar(...))` and `display(pd.DataFrame(...))`
  inside `with out_box:`. Both need new rendering paths: Plotly figures become JSON
  sent to the frontend; DataFrames become HTML strings.
- `display_warning` calls `display(HTML(...))` inside `with err_out:`. This becomes
  a separate JS call that appends to the warning panel.
- Parameter save/load (`save_params`, `load_params`) currently reads/writes CSV files
  and also round-trips through a `Textarea` widget. The file path is a user-supplied
  `Text` widget value. Both paths survive unchanged on the Python side; the frontend
  supplies the path string.
- The surrogate/link workaround (`wgt_surrogate`, `txt_surrogate`) exists only because
  setting a Dropdown value from an `on_click` callback was broken in the Jupyter
  environment. That entire mechanism is eliminated — HTML `<select>` elements have no
  such limitation.

---

## 2. Repository layout after conversion

```
e-orp/
├── main.py                  # entry point: starts PyWebView window
├── backend.py               # Api class exposed to JS; orchestrates worker thread
├── solver.py                # oorplp, oorp, three_peat, walk — unchanged
├── planner.py               # make_planning_datadict, tax tables, RMD — unchanged
├── renderer.py              # display_dd: produces JSON/HTML instead of display()
├── frontend/
│   ├── index.html           # single-page app shell
│   ├── style.css            # layout
│   └── app.js               # form binding, bridge calls, chart rendering
├── historical/
│   └── rates.csv            # unchanged
├── params/                  # unchanged
├── data/                    # unchanged
└── requirements.txt         # updated (see §3)
```

The existing notebook `e-ORP.ipynb` is kept as-is and continues to work. The
desktop app is an entirely additive set of files around the unchanged core logic.

---

## 3. Requirements file changes

**Remove** (Jupyter infrastructure no longer needed):
```
ipykernel
notebook
ipywidgets
ipython
nbformat
jupyterlab
jupyterlab_widgets
```

**Keep** (unchanged core):
```
pandas==2.2.3
plotly==6.1.0
pyscipopt==5.5.0
```

**Add**:
```
pywebview>=5.3          # native window + JS bridge; 5.x has stable threading API
```

Plotly is kept because `display_dd` uses `px.bar` and `px.line`. In the new
architecture, figures are serialized to JSON with `fig.to_json()` and rendered
in the browser pane by the Plotly JS library loaded from CDN — exactly the same
rendering engine, zero chart code changes.

---

## 4. Source file decomposition

The single 2,627-line notebook cell splits into four Python files along natural
boundaries that already exist in the code. The cuts are clean — there is no
circular dependency.

### 4.1 `planner.py` — pure computation, no UI references

Extract verbatim, lines 22–1401:

- Historical data loading (`hd = pd.read_csv(...)`, doubling/wrapping)
- All tax tables: `tax_rates`, `cgt_rates`, `tax_brk_*`, `cgt_brk_*`,
  `std_ded_*`, `IRMAA_buks`, `IRMAA_chgs`, `RMD_divisor`, `annual_QCD_limit_pp`
- Helper functions: `bkts_for_year`, `tax_bucket_n_size`, `cgt_bucket_n_size`,
  `obbba_pax_in_year`, `IRMAA_buk_n_size`, `IRMAA_chg_n_size`
- `set_nut`, `get_nut`
- `make_planning_datadict(params_dict)` — **one change only**: replace all
  `xxx_box.value` accesses with reads from a plain `params_dict` argument
  (see §5.1). All validation logic, all `display_warning()` calls, all
  computation is identical.

**One dependency to cut:** `display_warning` is called inside
`make_planning_datadict`. Replace the import with an injected callback:

```python
# planner.py
def make_planning_datadict(p, warn_cb=None):
    def display_warning(msg):
        if warn_cb: warn_cb(msg)
    ...
```

### 4.2 `solver.py` — SCIP wrapper, no UI references

Extract verbatim, lines 1404–2021:

- `VARS`, `BINS` lists
- `lop_to_cents`, `lop_to_cents_signed`
- `oorplp(dd, mode, objective, tout, glim)`

`oorplp` currently calls `display_warning` — apply the same injected callback
pattern as above.

### 4.3 `renderer.py` — output generation, produces data not widgets

Extract and adapt, lines 2022–2186 (`display_dd`):

```python
# renderer.py
import plotly.express as px
import pandas as pd

def render_dd(dd, fname=None):
    """
    Returns a list of output items in order:
      {'type': 'plotly', 'json': <fig.to_json()>}
      {'type': 'table',  'html': <df.to_html()>}
      {'type': 'heading','text': <str>}
      {'type': 'warning','text': <str>}
    """
    items = []
    ...
    # where display_dd had: display(px.bar(...))
    fig = px.bar(...)
    items.append({'type': 'plotly', 'json': fig.to_json()})
    # where it had: display(Markdown('### Heading'))
    items.append({'type': 'heading', 'text': 'Heading'})
    # where it had: display(pd.DataFrame(...))
    items.append({'type': 'table', 'html': df.to_html(classes='orp-table')})
    ...
    return items
```

`pd.options.display.max_columns = None` and `pd.options.display.precision = 3`
move to `renderer.py` initialisation. No chart logic changes — the exact same
`px.bar`/`px.line` calls with the same `color_discrete_map` and `barmode=`
arguments are used; only the final `display()` call is replaced.

### 4.4 `backend.py` — PyWebView Api class + worker thread

New file. Contains:

- `Api` class with all methods called from JS
- Worker thread management for the solver
- stdout/stderr capture queue for SCIP progress
- Parameter state (replaces widget state)

Detailed in §6.

### 4.5 `main.py` — entry point

New file, ~20 lines:

```python
import webview
from backend import Api

if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        'e-ORP — Optimal Retirement Planner',
        'frontend/index.html',
        js_api=api,
        width=1400,
        height=900,
        min_size=(900, 600)
    )
    webview.start(debug=False)
```

---

## 5. The parameter bridge

### 5.1 Replacing widget state with a plain dict

`make_planning_datadict` currently reads 70+ widget `.value` attributes
directly (e.g. `byear_box.value`, `rothl_box.value`). The refactored version
accepts a single `params_dict` argument keyed identically to the existing
`params` list in the notebook (column 0 of each row: `'byear'`, `'rorb'`,
`'rors'`, etc.).

The existing `params` list already defines the canonical parameter names and
defaults — it was designed for exactly this kind of serialization. The
replacement mapping is mechanical:

| Old | New |
|-----|-----|
| `byear_box.value` | `p['byear']` |
| `rorb_box.value` | `p['rorb']` |
| `rothl_box.value` | `p['rothl']` |
| `glide_box.value` | `p['glide']` |
| ... | ... |

The `params` list (lines 438–528) doubles as the default-value table and the
serialization schema. It is moved to `planner.py` as `PARAM_DEFAULTS`:

```python
PARAM_DEFAULTS = {
    'byear': 2024, 'rorb': 3.00, 'rors': 7.00, 'dvdd': 3.26,
    'frasa': 0.60, 'frasr': 0.60, 'frasd': 0.60,
    ...
}
```

### 5.2 Save/load compatibility

The existing CSV format produced by `save_params` is a pandas Series serialized
with `.to_csv()` — a two-column file with parameter names in column 0 and values
in column 0 (index). `load_params` reads it with
`pd.read_csv(..., index_col=0)` and accesses `ps.loc[key]['0']`.

This format is **preserved exactly** so existing parameter files continue to
work. `save_params` and `load_params` are ported to `backend.py` operating on
`self.params` dict rather than widget values:

```python
def save_params(self, filepath):
    ps = pd.Series(self.params)
    ps.to_csv(filepath)
    return {'ok': True}

def load_params(self, filepath):
    ps = pd.read_csv(filepath, index_col=0, keep_default_na=False)
    for key in PARAM_DEFAULTS:
        if key in ps.index:
            self.params[key] = ps.loc[key]['0']
    return self.params   # return updated params to JS for form re-population
```

The `param_buf` Textarea (clipboard round-trip) becomes a JS-side operation:
the frontend calls `save_params` with a special sentinel path to get the CSV
string, or calls `load_params` with the CSV text passed as a string argument
rather than a file path.

---

## 6. `backend.py` — the Api class in detail

```python
import threading, queue, sys, io
import webview
from planner import make_planning_datadict, PARAM_DEFAULTS
from solver import oorplp
from renderer import render_dd
from high_level import oorp, three_peat, walk   # from solver.py

class Api:
    def __init__(self):
        self.params = dict(PARAM_DEFAULTS)
        self._log_queue = queue.Queue()
        self._result_queue = queue.Queue()
        self._running = False
        self.window = None   # set by main.py after window creation

    # ── Parameter management ──────────────────────────────────────────────

    def get_params(self):
        return self.params

    def set_params(self, params_dict):
        self.params.update(params_dict)
        return {'ok': True}

    def save_params(self, filepath):
        ...   # as in §5.2

    def load_params(self, filepath):
        ...   # as in §5.2

    # ── Run control ───────────────────────────────────────────────────────

    def run_projection(self, mode, testmode, tout, glim, efname):
        if self._running:
            return {'error': 'already running'}
        self._running = True
        t = threading.Thread(
            target=self._run_worker,
            args=(mode, testmode, tout, glim, efname),
            daemon=True
        )
        t.start()
        return {'ok': True}

    def _run_worker(self, mode, testmode, tout, glim, efname):
        warnings = []
        def warn_cb(msg):
            warnings.append(msg)
            self.window.evaluate_js(
                f"appendWarning({json.dumps(msg)})"
            )

        # Redirect stdout to capture SCIP output
        old_stdout = sys.stdout
        sys.stdout = _QueueWriter(self._log_queue)
        try:
            dd = make_planning_datadict(self.params, warn_cb=warn_cb)
            if testmode == 4:
                walk(mode, tout, glim, efname, warn_cb=warn_cb)
            elif testmode == 3:
                three_peat(mode, tout, glim, efname, warn_cb=warn_cb)
            else:
                objt = 'net_pretax' if testmode == 2 else 0
                test = 'test_losses' if testmode == 1 else ''
                oorp(mode, objt, test, tout, glim, efname, warn_cb=warn_cb)
            items = render_dd(dd, efname)
            self.window.evaluate_js(
                f"renderResults({json.dumps(items)})"
            )
        except Exception as e:
            import traceback
            self.window.evaluate_js(
                f"appendWarning({json.dumps(traceback.format_exc())})"
            )
        finally:
            sys.stdout = old_stdout
            self._running = False
            self.window.evaluate_js("runFinished()")

    def poll_log(self):
        """JS polls this ~200ms for SCIP progress text"""
        lines = []
        try:
            while True:
                lines.append(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        return '\n'.join(lines)


class _QueueWriter:
    def __init__(self, q): self.q = q
    def write(self, s):
        if s.strip(): self.q.put(s)
    def flush(self): pass
```

**Thread safety note:** `window.evaluate_js()` is safe to call from a worker
thread in PyWebView 5.x — it posts to the main-thread event loop internally.
The `poll_log` approach avoids a tight coupling between the worker and the
window event loop for the high-frequency SCIP log text.

---

## 7. Frontend architecture

### 7.1 `index.html` skeleton

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="style.css">
  <!-- Plotly JS — same rendering engine as Python plotly -->
  <script src="https://cdn.plot.ly/plotly-3.0.0.min.js"></script>
</head>
<body>
  <div id="app">
    <section id="inputs-panel">
      <!-- Form sections matching winputs layout — see §7.2 -->
    </section>
    <section id="controls-panel">
      <!-- mode, testmode, tout, glim, efname, Run button -->
    </section>
    <section id="warnings-panel"></section>
    <section id="scip-log-panel"></section>
    <section id="results-panel">
      <!-- charts and tables injected here by renderResults() -->
    </section>
  </div>
  <script src="app.js"></script>
</body>
</html>
```

### 7.2 Form layout

The `winputs` VBox/GridBox structure maps directly to HTML sections with CSS
Grid. Each `widgets.GridBox(children, layout=Layout(grid_template_columns=...))` 
becomes a `<div class="grid-NNN">` with matching `grid-template-columns` in CSS.
The visual sections are:

| ipywidgets section | HTML section id |
|--------------------|-----------------|
| Model Parameters header | `#section-model` |
| Person / Spouse ages and horizon | `#section-ages` |
| Asset Values | `#section-assets` |
| Social Security | `#section-ssa` |
| Pensions | `#section-pension` |
| Other Income | `#section-income` |
| Phases: Spending Model | `#section-spend` |
| Phases: Essential Spending (8 rows) | `#section-events` |
| Asset Allocation & Glide Path | `#section-alloc` |
| Rates | `#section-rates` |
| Taxes | `#section-taxes` |
| Modeling Assumptions | `#section-assumptions` |
| Parameter Save & Load | `#section-params` |

Widget-to-HTML element mapping:

| ipywidgets type | HTML element | Notes |
|-----------------|--------------|-------|
| `BoundedIntText` | `<input type="number" min=… max=… step=1>` | |
| `BoundedFloatText` | `<input type="number" min=… max=… step=…>` | |
| `Dropdown` | `<select>` | Options and values match exactly |
| `Checkbox` | `<input type="checkbox">` | Not used (glide uses Dropdown) |
| `ToggleButtons` | `<div>` of radio buttons | Not present in current UI |
| `Text` | `<input type="text">` | pfname, efname |
| `Textarea` | `<textarea>` | param_buf |
| `Button` | `<button>` | |
| `Label` | `<label>` or `<span>` | |

The `on_glide_change` observer becomes a plain JS `change` event listener on
the glide `<select>` that enables/disables the horizon allocation inputs —
identical logic, native HTML, no framework needed.

### 7.3 `app.js` — bridge calls and rendering

```javascript
// ── Startup ──────────────────────────────────────────────────────────────

window.addEventListener('pywebviewready', async () => {
    const params = await pywebview.api.get_params();
    populateForm(params);
    startLogPolling();
});

// ── Parameter sync ────────────────────────────────────────────────────────

function collectParams() {
    // Read all form inputs by their name attribute (matching PARAM_DEFAULTS keys)
    const params = {};
    document.querySelectorAll('[data-param]').forEach(el => {
        const key = el.dataset.param;
        params[key] = el.type === 'number' ? parseFloat(el.value) : el.value;
    });
    return params;
}

function populateForm(params) {
    document.querySelectorAll('[data-param]').forEach(el => {
        const key = el.dataset.param;
        if (key in params) el.value = params[key];
    });
    updateGlidePath();
}

// ── Run button ────────────────────────────────────────────────────────────

document.getElementById('run-button').addEventListener('click', async () => {
    const params = collectParams();
    await pywebview.api.set_params(params);

    document.getElementById('run-button').disabled = true;
    document.getElementById('run-button').textContent = 'Running...';
    document.getElementById('warnings-panel').innerHTML = '';
    document.getElementById('results-panel').innerHTML = '';
    document.getElementById('scip-log-panel').textContent = '';

    await pywebview.api.run_projection(
        parseInt(document.getElementById('nlpomode').value),
        parseInt(document.getElementById('testmode').value),
        parseFloat(document.getElementById('tout').value),
        parseFloat(document.getElementById('glim').value),
        document.getElementById('efname').value
    );
});

// ── Called by Python worker when run completes ────────────────────────────

function runFinished() {
    document.getElementById('run-button').disabled = false;
    document.getElementById('run-button').textContent = 'Run Projection';
}

// ── SCIP log polling ──────────────────────────────────────────────────────

function startLogPolling() {
    setInterval(async () => {
        const text = await pywebview.api.poll_log();
        if (text) {
            const el = document.getElementById('scip-log-panel');
            el.textContent += text;
            el.scrollTop = el.scrollHeight;
        }
    }, 200);
}

// ── Warning injection (called directly from Python) ───────────────────────

function appendWarning(msg) {
    const el = document.getElementById('warnings-panel');
    el.innerHTML += `<div class="warning">${msg}</div>`;
}

// ── Results rendering (called directly from Python) ───────────────────────

function renderResults(items) {
    const panel = document.getElementById('results-panel');
    panel.innerHTML = '';
    items.forEach((item, idx) => {
        if (item.type === 'plotly') {
            const div = document.createElement('div');
            div.id = `chart-${idx}`;
            div.className = 'chart';
            panel.appendChild(div);
            const fig = JSON.parse(item.json);
            Plotly.newPlot(div.id, fig.data, fig.layout, {responsive: true});
        } else if (item.type === 'table') {
            const div = document.createElement('div');
            div.className = 'table-wrapper';
            div.innerHTML = item.html;
            panel.appendChild(div);
        } else if (item.type === 'heading') {
            const h3 = document.createElement('h3');
            h3.textContent = item.text;
            panel.appendChild(h3);
        }
    });
}

// ── Glide path enable/disable (replaces on_glide_change observe) ──────────

function updateGlidePath() {
    const enabled = document.getElementById('glide').value === '1';
    ['frhsd','frhsr','frhsa','frhbd','frhbr','frhba'].forEach(id => {
        document.getElementById(id).disabled = !enabled;
    });
}
document.getElementById('glide').addEventListener('change', updateGlidePath);

// ── Save / Load params ────────────────────────────────────────────────────

document.getElementById('save-button').addEventListener('click', async () => {
    const path = document.getElementById('pfname').value;
    await pywebview.api.set_params(collectParams());
    await pywebview.api.save_params(path);
});

document.getElementById('load-button').addEventListener('click', async () => {
    const path = document.getElementById('pfname').value;
    const params = await pywebview.api.load_params(path);
    populateForm(params);
});

document.getElementById('copy-button').addEventListener('click', async () => {
    await pywebview.api.set_params(collectParams());
    const csv = await pywebview.api.get_params_csv();
    document.getElementById('param-buf').value = csv;
});

document.getElementById('paste-button').addEventListener('click', async () => {
    const csv = document.getElementById('param-buf').value;
    const params = await pywebview.api.load_params_from_csv(csv);
    populateForm(params);
});
```

---

## 8. Threading model and the `run_oorp` replacement

The current `run_oorp` callback runs synchronously on the Jupyter kernel thread.
The ipywidgets frontend remains live during the solve because the browser and
kernel are separate processes connected by WebSockets.

In PyWebView, the JS bridge call from the frontend to Python runs on the main
thread by default. If `run_projection` performed the solve directly, the window
would freeze for the entire solver duration. The design in §6 addresses this:

```
Main thread (PyWebView event loop)
  └── window.evaluate_js(...)        ← safe from any thread

Worker thread (daemon)
  ├── make_planning_datadict(...)
  ├── oorplp / oorp / three_peat / walk
  │     └── stdout → _QueueWriter → _log_queue
  ├── render_dd(dd)
  └── window.evaluate_js("renderResults(...)")   ← posts to main thread
  
JS polling timer (every 200ms)
  └── pywebview.api.poll_log()       ← drains _log_queue, updates scip-log-panel
```

`run_projection` returns `{'ok': True}` immediately after launching the thread,
so the JS `await` resolves quickly and the Run button shows "Running..." while
work proceeds asynchronously. `runFinished()` is called by the worker at
completion to restore the button state.

This replaces `time.sleep(1.0)` entirely — the 200ms poll gives near-real-time
SCIP progress display with no blocking.

---

## 9. Known issues to resolve during conversion

### 9.1 `wgt._options_values` (existing bug, already flagged)

`wgt_surrogate` accesses `wgt._options_values` (private attribute). This entire
mechanism is eliminated in the conversion — there is no Dropdown/callback
incompatibility in plain HTML. No porting work needed; it simply disappears.

### 9.2 `make_planning_datadict` reads widget globals directly

The function references 70+ module-level `xxx_box` variables. The refactor to
accept `params_dict` is the largest mechanical change in the conversion. It is
purely a search-and-replace: every `xxx_box.value` becomes `p['xxx']`, where
`'xxx'` is the key from the `params` list. The mapping is 1:1 and fully defined
by the existing `params` list (lines 438–528 in the notebook). No logic changes.

### 9.3 `display_warning` called inside `make_planning_datadict` and `oorplp`

Both functions call the module-level `display_warning`, which uses the
`err_out` Output widget. The injected `warn_cb` pattern (§4.1) decouples this.
In the desktop app, warnings appear in the warnings panel immediately via
`evaluate_js`. In the Jupyter notebook (unchanged), the existing `display_warning`
continues to work as before.

### 9.4 `oorp`, `three_peat`, `walk` call `display_dd` directly

Each of these high-level functions calls `display_dd(dd, fname)` at its
conclusion. In the refactored code, they instead return `dd` and the caller
(`_run_worker`) calls `render_dd(dd, fname)`. This requires adding `return dd`
to `oorp`, `three_peat`, and `walk` — a three-line change.

Alternatively, inject a `render_cb` parameter analogous to `warn_cb`. Either
approach works; returning `dd` is simpler.

### 9.5 Plotly figure JSON size

Each `fig.to_json()` for a retirement-horizon bar chart with 5 series × 30 years
is approximately 15–40 KB. Ten charts total ≈ 200–400 KB as a single JSON
payload. This is well within `evaluate_js` limits (PyWebView has no practical
payload size limit for local content) and renders in under 100ms in Plotly JS.

### 9.6 DataFrame `.to_html()` styling

`pd.DataFrame.to_html(classes='orp-table')` produces a standard HTML table.
The current Jupyter output uses pandas' built-in CSS for table formatting.
A small CSS rule in `style.css` (borders, font size, alternating row colours)
replaces this. The `pd.options.display.precision = 3` option carries over.

### 9.7 `from_eTaxd` / `from_jTaxd` naming inconsistency in `display_dd`

The comment in `display_dd` at the Real Withdrawals table (line ~2175) uses
`'from_eTaxd'` and `'from_jTaxd'` — consistent with the rest of the code. No
issue here; mentioned for completeness.

### 9.8 PyWebView backend exposure security

`pywebview` exposes all public methods of the `Api` class to JavaScript. In a
local desktop app with no network exposure this is acceptable. For clarity, name
any internal helpers with a leading underscore (e.g. `_run_worker`) so they are
not exposed.

---

## 10. Migration sequence

The work is organized in five stages. Each stage leaves the notebook fully
functional; the desktop app becomes runnable at the end of Stage 3 and
feature-complete at Stage 5.

### Stage 1 — Extract and test core logic (no UI changes)

1. Create `planner.py`: copy lines 22–1401, replace `xxx_box.value` with
   `p['xxx']`, add `warn_cb` injection, define `PARAM_DEFAULTS`.
2. Create `solver.py`: copy lines 1404–2021, add `warn_cb` injection.
3. Write `test_planner.py`: construct a `params_dict` from `PARAM_DEFAULTS`,
   call `make_planning_datadict`, verify `dd` structure matches the notebook
   output. The existing `dd_test_revised.ipynb` can validate the solver output.
4. Verify `solver.py` runs `oorplp` cleanly when called from the test script.

**Exit criterion:** `python test_planner.py` passes; `dd_test_revised.ipynb`
passes against output from the new `solver.py`.

### Stage 2 — Create renderer

1. Create `renderer.py`: adapt `display_dd` (lines 2022–2186) to return a list
   of typed items instead of calling `display()`.
2. Verify chart JSON round-trips: `json.loads(fig.to_json())` should be
   accepted by `Plotly.newPlot` without modification.
3. Verify table HTML: `df.to_html()` output renders correctly in a browser.

**Exit criterion:** `render_dd(dd)` returns correct items; manual browser test
of the HTML confirms chart and table appearance.

### Stage 3 — Minimal working desktop app

1. Write `backend.py` with `Api` class (§6), worker thread, log queue.
2. Write `main.py` (§4.5).
3. Write `frontend/index.html`: minimal form with all `data-param` attributes
   but minimal styling — just enough to confirm the bridge works.
4. Write `frontend/app.js`: `pywebviewready` handler, `collectParams`,
   `run_projection` call, `renderResults` stub (just logs to console).
5. Install PyWebView in the venv: `pip install "pywebview>=5.3"`.
6. Run `python main.py`, set defaults, click Run, verify solver executes and
   results return without freezing the window.

**Exit criterion:** Window opens, Run button triggers solver in background,
SCIP log appears in the log panel, basic results render without error.

### Stage 4 — Full form and results UI

1. Build out all form sections in `index.html` matching the widget layout (§7.2).
2. Style with `style.css`: grid layout, section borders matching the existing
   widget `Layout` borders.
3. Implement all `app.js` event handlers: glide path enable/disable, save/load
   buttons, param buffer copy/paste.
4. Implement full `renderResults` in `app.js`: Plotly charts with `responsive:true`,
   table HTML insertion, heading elements.
5. Implement `appendWarning` and connect to Python `warn_cb`.

**Exit criterion:** All form fields present, values persist across save/load,
all 9 charts render, all tables appear, warnings display correctly.

### Stage 5 — Polish and venv finalization

1. Update `requirements.txt` as per §3.
2. Test on a fresh venv: `python -m venv .venv && pip install -r requirements.txt`.
3. Test parameter file round-trip: save from notebook, load in desktop app and
   vice versa.
4. Test all five `testmode` values (Normal, Artificial Losses, Alternate
   Objective, 3-peat, Random Walk).
5. Verify `historical/rates.csv` lookup works in both environments.
6. Address the `wgt._options_values` issue in the notebook (replace with
   `wgt.options`) as a separate notebook-side fix.

**Exit criterion:** Both the notebook and `python main.py` produce identical
numerical output for the same parameter file; `requirements.txt` installs
cleanly from scratch.

---

## 11. What is explicitly not changed

- `oorplp` — the entire SCIP model formulation (lines 1501–2021), all
  constraints, all variables, all objective functions. Zero changes.
- All tax tables and bracket logic.
- `historical/rates.csv` format and loading.
- The parameter CSV file format (backward compatible with existing saved files).
- `three_peat`, `walk`, `walk_lap` logic.
- The `display_dd` chart definitions — same `px.bar`/`px.line` calls, same
  `color_discrete_map`, same `barmode='relative'`.
- `dd_test_revised.ipynb` — continues to work against the unchanged solver.
- The notebook itself — it continues to function in Jupyter independently.
