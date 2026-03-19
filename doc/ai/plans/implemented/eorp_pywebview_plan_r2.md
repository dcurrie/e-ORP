# e-ORP: Conversion Plan — Jupyter/ipywidgets → PyWebView (Revision 2)

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
- `three_peat` produces a summary table and statistics dict (`sm`) rather than
  calling `display_dd`; it needs its own renderer function (§4.3).
- `display_warning` calls `display(HTML(...))` inside `with err_out:`. This becomes
  a separate JS call appending to the warning panel.
- Parameter save/load (`save_params`, `load_params`) reads/writes CSV files and
  also round-trips through a `Textarea` widget. Both paths survive unchanged on
  the Python side; the frontend supplies the path string or CSV text.
- The surrogate/link workaround (`wgt_surrogate`, `txt_surrogate`) exists only
  because setting a Dropdown value from an `on_click` callback was broken in the
  Jupyter environment. That entire mechanism is eliminated — HTML `<select>`
  elements have no such limitation.

---

## 2. Repository layout after conversion

```
e-orp/
├── main.py                  # entry point: starts PyWebView window
├── backend.py               # Api class exposed to JS; orchestrates worker thread
├── solver.py                # oorplp, oorp, three_peat, walk, walk_lap — unchanged
├── planner.py               # make_planning_datadict, tax tables, RMD, squirrel_map
├── renderer.py              # render_dd, render_three_peat: produce JSON/HTML items
├── frontend/
│   ├── index.html           # single-page app shell
│   ├── style.css            # layout
│   ├── app.js               # form binding, bridge calls, chart rendering
│   └── plotly.min.js        # bundled Plotly JS (see §3 — offline operation)
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
in the browser pane by the Plotly JS library — exactly the same rendering
engine, zero chart code changes.

**Plotly JS bundling:** Ship `plotly.min.js` alongside the app rather than
loading from CDN. e-ORP is a desktop tool intended for offline use; a CDN
dependency would break the app without internet. Download the matching Plotly JS
release (plotly.js v2.x corresponding to Python plotly 6.1.0) once and commit
it to `frontend/`. Reference it in `index.html` as a relative path.

---

## 4. Source file decomposition

The single 2,627-line notebook cell splits into five Python files along natural
boundaries that already exist in the code. The cuts are clean — there is no
circular dependency.

### 4.1 `planner.py` — pure computation, no UI references

Extract verbatim, lines 22–1401, with the following targeted changes:

**Shared data loaded at module level:**
```python
import os, pandas as pd

_here = os.path.dirname(os.path.abspath(__file__))
hd = pd.read_csv(os.path.join(_here, 'historical', 'rates.csv'), index_col='year')
min_hd_year = min(hd.index)
max_hd_year = max(hd.index)
hd = pd.concat([hd,
                 hd.copy().set_index(pd.Index(
                     (x + max_hd_year - min_hd_year + 1
                      for x in range(min_hd_year, max_hd_year + 1)),
                     name='year'))])
```

`hd`, `min_hd_year`, and `max_hd_year` are module-level in `planner.py` and
imported by `solver.py` with `from planner import hd, min_hd_year, max_hd_year`.
This matches how the notebook uses them: defined once at startup, shared by
`make_planning_datadict`, `three_peat`, and `walk`.

Using an absolute path (via `__file__`) means the app works regardless of the
working directory from which it is launched.

**`squirrel_map`, `set_nut`, `get_nut`** (lines 961–981) also live in
`planner.py` and are imported by `solver.py`.

**`make_planning_datadict` — full refactored signature:**
```python
def make_planning_datadict(p, test_mode='', historical_year_for_rates=None,
                           warn_cb=None):
```

Where `p` is the `params_dict` argument and `warn_cb` is the injected warning
callback. The three existing call patterns map to:

| Existing call | Refactored call |
|---|---|
| `make_planning_datadict(test)` | `make_planning_datadict(p, test_mode=test)` |
| `make_planning_datadict(test, fromyear)` | `make_planning_datadict(p, test_mode=test, historical_year_for_rates=fromyear)` |
| `make_planning_datadict('3-peat')` | `make_planning_datadict(p, test_mode='3-peat')` |

All `xxx_box.value` accesses inside the function body become `p['xxx']` — a
mechanical substitution keyed by the `params` list (lines 438–528). The
`display_warning` calls become:

```python
def display_warning(msg):
    if warn_cb:
        warn_cb(msg)

# Replace module-level display_warning with injected one inside the function body
```

**`PARAM_DEFAULTS`:** The `params` list in the notebook (lines 438–528) has
systematic errors in its default value column — it stores fractions (0.02) for
parameters the widgets store as percentages (2.0), and has obviously wrong
defaults for `xinc`, `xinr`, and `spndm`. These are latent bugs in the existing
notebook (the defaults are only used as fallbacks when a key is missing from a
saved CSV file). `PARAM_DEFAULTS` in `planner.py` must use the actual widget
defaults:

```python
PARAM_DEFAULTS = {
    # Rates — stored as percent in widgets and CSV; /100 done inside make_planning_datadict
    'rorb':  3.0,   'rors':  7.0,   'dvdd':  3.26,
    'infl':  2.0,   'infs':  4.0,   # NOT 0.02/0.04 — those are the wrong fraction values
    # Asset allocation — stored as percent (60.0 not 0.60)
    'frasa': 60.0,  'frasr': 60.0,  'frasd': 60.0,
    'fraba': 40.0,  'frabr': 40.0,  'frabd': 40.0,
    'frhsa': 60.0,  'frhsr': 60.0,  'frhsd': 60.0,
    'frhba': 40.0,  'frhbr': 40.0,  'frhbd': 40.0,
    # Spending
    'spndm': 0,     # 0 = Traditional (TSM) — NOT 1.00
    'incn':  50.0,  'infs':  4.0,   'chty':  0.0,
    'xinc':  1.0,   # NOT 2024 — widget default is 1
    'xinr':  0.0,   # NOT 2024 — widget default is 0.0
    # Ages and horizon
    'byear': 2024,
    'aage1': 65,    'aage2': 65,
    'fage1': 92,    'fage2': 92,
    # Assets ($000s)
    'atax1': 50.0,  'atax2': 50.0,
    'bsis1': 10.0,  'bsis2': 10.0,
    'taxd1': 100.0, 'taxd2': 100.0,
    'roth1': 100.0, 'roth2': 100.0,
    # SSA
    'ssar1': 36.0,  'ssar2': 36.0,
    'refa1': 65,    'refa2': 65,
    'reta1': 70,    'reta2': 65,
    # Pension
    'popt1': 0,     'popt2': 0,
    'pens1': 0.0,   'pens2': 0.0,
    'page1': 65,    'page2': 65,
    'pinh1': 0.0,   'pinh2': 0.0,
    # Tax / MAGI
    'magib': 42.0,  'magip': 40.0,
    'fstat': 1,     'ftab':  0.0,
    # Events (8 rows)
    'yr01': 2025, 'yr02': 2025, 'yr03': 2025, 'yr04': 2025,
    'yr05': 2025, 'yr06': 2025, 'yr07': 2025, 'yr08': 2025,
    'pr01': 0, 'pr02': 0, 'pr03': 0, 'pr04': 0,
    'pr05': 0, 'pr06': 0, 'pr07': 0, 'pr08': 0,
    'va01': 0.0, 'va02': 0.0, 'va03': 0.0, 'va04': 0.0,
    'va05': 0.0, 'va06': 0.0, 'va07': 0.0, 'va08': 0.0,
    'tx01': '', 'tx02': '', 'tx03': '', 'tx04': '',
    'tx05': '', 'tx06': '', 'tx07': '', 'tx08': '',
    # Other
    'glide': 0,     'ssabr': 1,
    'rothl': 'unlimited',
    'hist':  'Use Values Below',
}
```

The existing `params` list default column bugs affect only the missing-key
fallback path in `load_params`. Existing saved CSV files are unaffected because
they contain the actual percent values written by `save_params`.

### 4.2 `solver.py` — SCIP wrapper and high-level run functions

Extract verbatim, lines 1404–2580 (everything from `VARS` through the end of
`three_peat`), with the following targeted changes:

**Imports at top of file:**
```python
from planner import (make_planning_datadict, hd, set_nut, get_nut,
                     squirrel_map, PARAM_DEFAULTS)
import statistics, pandas as pd
```

**`warn_cb` injection:** `oorplp` calls `display_warning`; apply the same
injected callback pattern used in `planner.py`.

**`hist_box` references removed:** Both `walk()` and `three_peat()` read
`hist_box.value` directly:

```python
# In three_peat (original):
if hist_box.value != 'Use Values Below':
    historical_year_for_rates = int(hist_box.value)

# In walk (original):
if hist_box.value != 'Use Values Below':
    sta_yr = int(hist_box.value)
```

Both functions must accept `params` as an argument and read `params['hist']`
instead. The refactored signatures are:

```python
def oorp(p, mode, objt, test, tout, glim, fname=None, warn_cb=None):
    dd = make_planning_datadict(p, test_mode=test, warn_cb=warn_cb)
    ...

def walk_lap(p, fromyear, mode, tout, glim, warn_cb=None):
    dd = make_planning_datadict(p, test_mode='', historical_year_for_rates=fromyear,
                                warn_cb=warn_cb)
    ...

def walk(p, mode, tout, glim, fname, warn_cb=None):
    sta_yr = 1970
    if p['hist'] != 'Use Values Below':
        sta_yr = int(p['hist'])
    ...

def three_peat(p, mode, tout, glim, fname, warn_cb=None):
    dd = make_planning_datadict(p, test_mode='3-peat', warn_cb=warn_cb)
    historical_year_for_rates = 1970
    if p['hist'] != 'Use Values Below':
        historical_year_for_rates = int(p['hist'])
    ...
```

**`output_cb` injection for progress messages:** `oorp`, `walk`, and
`three_peat` print per-iteration progress inside `with out_box:` and
`with drb_out:`. Replace all `with drb_out:` / `with out_box:` context
managers with direct `print()` calls — in the desktop app, stdout is already
redirected to the log queue by the worker (§6). The `err_out.clear_output()`
and `out_box.clear_output()` calls at the start of each function are simply
removed; the frontend clears the panels before starting a new run.

**Return values:** `oorp`, `three_peat`, and `walk` currently call
`display_dd(dd, fname)` or produce output inline. Refactor them to return
their result data for the caller (`_run_worker`) to render:

```python
# oorp returns:
return (dd, status, net_pretax, di, stage, gap, stime)

# walk returns:
return (worst_di_dd, worst_year, worst_di, fname)

# three_peat returns:
return (rf, sm, fname)   # rf = result DataFrame, sm = summary dict
```

**Fix the `if/if` bug in `run_oorp`:** The original has two separate `if`
statements, causing `walk` (testmode=4) to also invoke `oorp`. The corrected
`_run_worker` (§6) uses `if/elif/elif/else`.

### 4.3 `renderer.py` — output generation, produces data not widgets

New file. `display_dd` (lines 2022–2186) is adapted to `render_dd`, and a new
`render_three_peat` function handles `three_peat`'s distinct output. Both return
a list of typed items consumed by `renderResults()` in the frontend.

```python
# renderer.py
import plotly.express as px
import pandas as pd

pd.options.display.max_columns = None
pd.options.display.precision = 3

def render_dd(dd, fname=None):
    """
    Replaces display_dd. Returns a list of output items:
      {'type': 'plotly',  'json': <fig.to_json()>}
      {'type': 'table',   'html': <df.to_html()>}
      {'type': 'heading', 'text': <str>}
    """
    items = []
    dfr = pd.DataFrame(dd, index=dd['year'])
    if fname:
        dfr.to_csv(fname)
    df = pd.DataFrame(dfr[1:])

    # Each display(px.bar/line(...)) call becomes:
    fig = px.bar(df, barmode='relative', x='year',
                 y=['afterTax', 'e_Taxd', 'j_Taxd', 'e_Roth', 'j_Roth'],
                 color_discrete_map={...},
                 title='Nominal Balances')
    items.append({'type': 'plotly', 'json': fig.to_json()})

    # Each display(Markdown('### Heading')) becomes:
    items.append({'type': 'heading', 'text': 'Nominal Balances'})

    # Each display(pd.DataFrame(...)) becomes:
    items.append({'type': 'table',
                  'html': pd.DataFrame(df, columns=[...]).to_html(
                      classes='orp-table', border=0)})
    ...
    return items


def render_three_peat(rf, sm):
    """
    Replaces the with out_box: display block at the end of three_peat.
    rf: the real-values result DataFrame (rs rows 1..i)
    sm: the summary statistics dict
    Returns a list of typed items.
    """
    items = []
    items.append({'type': 'heading', 'text': '3-Peat Real Values (Base Year $000s)'})
    items.append({'type': 'table',
                  'html': pd.DataFrame(rf, columns=[
                      'year', 'e', 'j', 'hist_year', 'ror_stock', 'dvd_stock',
                      'ror_bonds', 'infl_rate', 'TAB', 'x_RothConv', 'deposits',
                      'withdrawals', 'IRMAA', 'income_tax', 'disp_income'
                  ]).to_html(classes='orp-table', border=0)})
    # sm is a plain dict — render as a small key/value table
    sm_df = pd.DataFrame([sm])
    items.append({'type': 'table', 'html': sm_df.to_html(classes='orp-table', border=0)})
    return items
```

All nine chart definitions (7 `px.bar` + 2 `px.line`) in `display_dd` are
copied verbatim into `render_dd`; only the `display(...)` wrapper is replaced
with `items.append(...)`.

### 4.4 `backend.py` — PyWebView Api class and worker thread

New file. Contains the `Api` class with all methods callable from JS, the worker
thread, stdout capture queue, and parameter state. See §6 for full detail.

### 4.5 `main.py` — entry point

```python
import os
import webview
from backend import Api

if __name__ == '__main__':
    api = Api()
    html_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'frontend', 'index.html'
    )
    window = webview.create_window(
        'e-ORP — Optimal Retirement Planner',
        html_path,
        js_api=api,
        width=1400,
        height=900,
        min_size=(900, 600)
    )
    api.window = window   # must be set before webview.start() — worker uses it
    webview.start(debug=False)
```

The `api.window = window` assignment is required because `_run_worker` calls
`self.window.evaluate_js(...)` from the background thread. PyWebView 5.x makes
`evaluate_js` safe to call from non-main threads by posting to the main event
loop internally.

---

## 5. The parameter bridge

### 5.1 Replacing widget state with a plain dict

`make_planning_datadict` currently reads 89 widget `.value` attributes directly.
The refactored version accepts a single `p` dict keyed identically to the `params`
list. The substitution is mechanical:

| Old | New |
|-----|-----|
| `byear_box.value` | `p['byear']` |
| `rothl_box.value` | `p['rothl']` |
| `glide_box.value` | `p['glide']` |
| `ssabr_box.value == 1` | `p['ssabr'] == 1` |
| ... 85 more ... | ... |

No logic changes; only the source of each value changes.

### 5.2 Historical year dropdown population

`hist_box` options are built dynamically from `min_hd_year` / `max_hd_year`
derived from `historical/rates.csv`. The frontend cannot know these values
without being told. The `Api` class exposes:

```python
def get_hist_options(self):
    from planner import min_hd_year, max_hd_year
    return {
        'min': int(min_hd_year),
        'max': int(max_hd_year)
    }
```

Called during `pywebviewready` startup; `app.js` populates the `hist`
`<select>` with `'Use Values Below'` plus the year range.

### 5.3 Save/load and clipboard API

The existing CSV format (`pd.Series.to_csv()`) produces a two-column file with
a string column named `'0'`. `load_params` correctly accesses it with
`ps.loc[key]['0']` — this column name is deterministic because `pd.Series` with
no `.name` attribute always serializes as column `0`. No change needed.

The full set of parameter API methods on `Api`:

```python
def get_params(self):
    return self.params

def set_params(self, params_dict):
    """Called by JS before run_projection to sync form state."""
    self.params.update(self._coerce_types(params_dict))
    return {'ok': True}

def save_params(self, filepath):
    ps = pd.Series(self.params)
    ps.to_csv(filepath)
    return {'ok': True}

def load_params(self, filepath):
    ps = pd.read_csv(filepath, index_col=0, keep_default_na=False)
    for key in PARAM_DEFAULTS:
        if key in ps.index:
            self.params[key] = self._coerce_one(key, ps.loc[key]['0'])
    return self.params   # returned to JS for form re-population

def get_params_csv(self):
    """Return params as CSV string for clipboard copy."""
    return pd.Series(self.params).to_csv(None)

def load_params_from_csv(self, csv_string):
    """Load params from CSV text (clipboard paste). Returns updated params."""
    from io import StringIO
    ps = pd.read_csv(StringIO(csv_string), index_col=0, keep_default_na=False)
    for key in PARAM_DEFAULTS:
        if key in ps.index:
            self.params[key] = self._coerce_one(key, ps.loc[key]['0'])
    return self.params

def get_hist_options(self):
    from planner import min_hd_year, max_hd_year
    return {'min': int(min_hd_year), 'max': int(max_hd_year)}
```

### 5.4 Parameter type coercion

All HTML form values arrive in JS as strings. The `set_params` and
`load_params` methods call `_coerce_types` to restore the correct Python types
before `make_planning_datadict` uses them. A type map is defined once in
`backend.py`:

```python
# Centralized type map — derived from params list analysis
_INT_PARAMS = {
    'byear', 'aage1', 'aage2', 'fage1', 'fage2', 'refa1', 'refa2',
    'reta1', 'reta2', 'page1', 'page2',
    'yr01','yr02','yr03','yr04','yr05','yr06','yr07','yr08',
    'fstat', 'glide', 'spndm', 'ssabr',
    'pr01','pr02','pr03','pr04','pr05','pr06','pr07','pr08',
    'popt1','popt2'
}
_STR_PARAMS = {
    'tx01','tx02','tx03','tx04','tx05','tx06','tx07','tx08',
    'rothl', 'hist'
}
# All remaining 46 params are float

def _coerce_one(self, key, val):
    if key in _INT_PARAMS:
        return int(float(val))    # int(float()) handles '1.0' → 1 safely
    if key in _STR_PARAMS:
        return str(val)
    return float(val)

def _coerce_types(self, d):
    return {k: self._coerce_one(k, v) for k, v in d.items()}
```

The `int(float(val))` pattern handles the case where a numeric string like
`'1.0'` arrives from a form's `<select>` element.

---

## 6. `backend.py` — the Api class in detail

```python
import threading, queue, sys, json, os
import pandas as pd
import webview
from planner import make_planning_datadict, PARAM_DEFAULTS, min_hd_year, max_hd_year
from solver import oorplp, oorp, three_peat, walk
from renderer import render_dd, render_three_peat

_INT_PARAMS = { ... }   # as defined in §5.4
_STR_PARAMS = { ... }

class Api:
    def __init__(self):
        self.params = dict(PARAM_DEFAULTS)
        self._log_queue = queue.Queue()
        self._running = False
        self.window = None      # set by main.py immediately after create_window

    # ── Parameter management ──────────────────────────────────────────────
    # (all methods from §5.3 and §5.4)

    # ── Run control ───────────────────────────────────────────────────────

    def run_projection(self, mode, testmode, tout, glim, efname):
        """Called from JS Run button. Returns immediately; work runs in thread."""
        if self._running:
            return {'error': 'already running'}
        self._running = True
        t = threading.Thread(
            target=self._run_worker,
            args=(int(mode), int(testmode), float(tout), float(glim), str(efname)),
            daemon=True
        )
        t.start()
        return {'ok': True}

    def _run_worker(self, mode, testmode, tout, glim, efname):
        def warn_cb(msg):
            self.window.evaluate_js(
                f'appendWarning({json.dumps(msg)})'
            )
        old_stdout = sys.stdout
        sys.stdout = _QueueWriter(self._log_queue)
        try:
            # Fix for if/if bug in original run_oorp: use if/elif/elif/else
            if testmode == 4:
                result = walk(self.params, mode, tout, glim, efname,
                              warn_cb=warn_cb)
                (worst_dd, worst_year, worst_di, fname) = result
                items = render_dd(worst_dd, fname)
            elif testmode == 3:
                result = three_peat(self.params, mode, tout, glim, efname,
                                    warn_cb=warn_cb)
                (rf, sm, fname) = result
                items = render_three_peat(rf, sm)
            else:
                objt = 'net_pretax' if testmode == 2 else 0
                test = 'test_losses' if testmode == 1 else ''
                result = oorp(self.params, mode, objt, test, tout, glim,
                              fname=efname, warn_cb=warn_cb)
                (dd, status, net_pretax, di, stage, gap, stime) = result
                items = render_dd(dd, efname)

            # Pass JSON value (not string) to JS — no escaping issues
            self.window.evaluate_js(
                f'renderResults({json.dumps(items)})'
            )
        except Exception:
            import traceback
            self.window.evaluate_js(
                f'appendWarning({json.dumps(traceback.format_exc())})'
            )
        finally:
            sys.stdout = old_stdout
            self._running = False
            self.window.evaluate_js('runFinished()')  # always re-enables Run button

    def poll_log(self):
        """JS polls this ~200ms to drain SCIP progress text."""
        lines = []
        try:
            while True:
                lines.append(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        return '\n'.join(lines)


class _QueueWriter:
    """Redirects sys.stdout writes to a queue for JS polling."""
    def __init__(self, q): self.q = q
    def write(self, s):
        if s.strip(): self.q.put(s)
    def flush(self): pass
```

**`evaluate_js` and JSON payloads:** The pattern
`self.window.evaluate_js(f'renderResults({json.dumps(items)})')` is correct
and safe. `json.dumps(items)` produces a valid JSON value (not a string
literal), so it is also valid JavaScript syntax — the JS engine parses it as a
literal object. This is the standard PyWebView pattern for passing structured
data and avoids string-escaping issues entirely.

**Thread safety:** `window.evaluate_js()` is safe to call from a worker thread
in PyWebView 5.x. All three calls in `_run_worker` (`appendWarning`,
`renderResults`, `runFinished`) post to the main-thread event loop internally.

**Button re-enable on error:** The `runFinished()` call is in the `finally`
block, so the Run button is always re-enabled regardless of whether the solver
succeeds, fails, or raises an exception.

---

## 7. Frontend architecture

### 7.1 `index.html` skeleton

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="style.css">
  <script src="plotly.min.js"></script>  <!-- bundled, not CDN -->
</head>
<body>
  <div id="app">
    <section id="inputs-panel">
      <!-- All form sections — see §7.2 -->
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
becomes a `<div>` with matching `grid-template-columns` in CSS.

Widget-to-HTML element mapping:

| ipywidgets type | HTML element | Notes |
|---|---|---|
| `BoundedIntText` | `<input type="number" min=… max=… step=1>` | |
| `BoundedFloatText` | `<input type="number" min=… max=… step=…>` | |
| `Dropdown` | `<select>` | Options and integer values match exactly |
| `Text` | `<input type="text">` | pfname, efname, tx01–tx08 |
| `Textarea` | `<textarea rows=5>` | param_buf |
| `Button` | `<button>` | |
| `Label` | `<label>` or `<span>` | |

All form inputs carry a `data-param="key"` attribute matching their
`PARAM_DEFAULTS` key, used by `collectParams()` for bulk serialization.

The `on_glide_change` observer becomes a plain JS `change` event on the glide
`<select>` — identical logic, no framework needed.

The `hist` dropdown is populated at startup from `get_hist_options()`:

```javascript
window.addEventListener('pywebviewready', async () => {
    const opts = await pywebview.api.get_hist_options();
    const sel = document.getElementById('hist');
    const opt = document.createElement('option');
    opt.value = 'Use Values Below';
    opt.textContent = 'Use Values Below';
    sel.appendChild(opt);
    for (let y = opts.min; y <= opts.max; y++) {
        const o = document.createElement('option');
        o.value = String(y);
        o.textContent = String(y);
        sel.appendChild(o);
    }
    const params = await pywebview.api.get_params();
    populateForm(params);
    startLogPolling();
});
```

### 7.3 `app.js` — bridge calls and rendering

```javascript
// ── Parameter type map (mirrors backend._INT_PARAMS etc.) ────────────────

const INT_PARAMS = new Set([
    'byear','aage1','aage2','fage1','fage2','refa1','refa2','reta1','reta2',
    'page1','page2','yr01','yr02','yr03','yr04','yr05','yr06','yr07','yr08',
    'fstat','glide','spndm','ssabr',
    'pr01','pr02','pr03','pr04','pr05','pr06','pr07','pr08','popt1','popt2'
]);
const STR_PARAMS = new Set([
    'tx01','tx02','tx03','tx04','tx05','tx06','tx07','tx08','rothl','hist'
]);

function coerceParam(key, val) {
    if (INT_PARAMS.has(key))  return parseInt(val, 10);
    if (STR_PARAMS.has(key))  return String(val);
    return parseFloat(val);
}

// ── Form collection and population ───────────────────────────────────────

function collectParams() {
    const params = {};
    document.querySelectorAll('[data-param]').forEach(el => {
        const key = el.dataset.param;
        params[key] = coerceParam(key, el.value);
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
        document.getElementById('nlpomode').value,
        document.getElementById('testmode').value,
        document.getElementById('tout').value,
        document.getElementById('glim').value,
        document.getElementById('efname').value
    );
});

// ── Called from Python worker on completion ───────────────────────────────

function runFinished() {
    const btn = document.getElementById('run-button');
    btn.disabled = false;
    btn.textContent = 'Run Projection';
}

// ── SCIP log polling (replaces time.sleep(1.0) workaround) ───────────────

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

// ── Warning injection — called directly from Python via evaluate_js ───────

function appendWarning(msg) {
    const el = document.getElementById('warnings-panel');
    const div = document.createElement('div');
    div.className = 'warning';
    div.textContent = msg;   // textContent not innerHTML — avoids XSS from traceback
    el.appendChild(div);
}

// ── Results rendering — called directly from Python via evaluate_js ───────

function renderResults(items) {
    const panel = document.getElementById('results-panel');
    panel.innerHTML = '';
    items.forEach((item, idx) => {
        if (item.type === 'plotly') {
            const div = document.createElement('div');
            div.id = `chart-${idx}`;
            div.className = 'chart';
            panel.appendChild(div);
            // fig is already a parsed JS object — json.dumps in Python produced
            // a JSON value, not a string, so it arrives here already parsed
            Plotly.newPlot(div.id, item.json.data, item.json.layout,
                           {responsive: true});
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
    const enabled = parseInt(document.getElementById('glide').value) !== 0;
    ['frhsd','frhsr','frhsa','frhbd','frhbr','frhba'].forEach(id => {
        document.getElementById(id).disabled = !enabled;
    });
}
document.getElementById('glide').addEventListener('change', updateGlidePath);

// ── Save / Load ───────────────────────────────────────────────────────────

document.getElementById('save-button').addEventListener('click', async () => {
    await pywebview.api.set_params(collectParams());
    await pywebview.api.save_params(document.getElementById('pfname').value);
});

document.getElementById('load-button').addEventListener('click', async () => {
    const params = await pywebview.api.load_params(
        document.getElementById('pfname').value);
    populateForm(params);
});

document.getElementById('copy-button').addEventListener('click', async () => {
    await pywebview.api.set_params(collectParams());
    document.getElementById('param-buf').value =
        await pywebview.api.get_params_csv();
});

document.getElementById('paste-button').addEventListener('click', async () => {
    const params = await pywebview.api.load_params_from_csv(
        document.getElementById('param-buf').value);
    populateForm(params);
});
```

**Note on `renderResults` JSON handling:** When Python calls
`window.evaluate_js(f'renderResults({json.dumps(items)})')`, the argument is a
JSON value (object literal), not a string. So `item.json` in JavaScript is
already a parsed object — `JSON.parse()` is not needed. The chart JSON structure
produced by Plotly's `fig.to_json()` is directly compatible with
`Plotly.newPlot(div, fig.data, fig.layout)`.

---

## 8. Threading model and the `run_oorp` replacement

The current `run_oorp` callback runs synchronously on the Jupyter kernel thread.
The ipywidgets frontend remains live during the solve because the browser and
kernel are separate processes connected over WebSockets.

In PyWebView, a blocking bridge call from JS to Python would freeze the window
for the entire solver duration. The design in §6 avoids this:

```
Main thread (PyWebView event loop)
  └── window.evaluate_js(...)        ← safe to call from any thread

Worker thread (daemon)
  ├── make_planning_datadict(p, ...)
  ├── oorp / three_peat / walk
  │     ├── oorplp (SCIP solver)
  │     └── stdout → _QueueWriter → _log_queue
  ├── render_dd / render_three_peat
  └── window.evaluate_js("renderResults(...)")  ← posts to main thread

JS polling timer (200 ms interval)
  └── pywebview.api.poll_log()  ← drains _log_queue, appends to log panel
```

`run_projection` returns `{'ok': True}` immediately after launching the thread,
so the JS `await` resolves quickly and the Run button shows "Running..." while
work proceeds asynchronously. `runFinished()` (in the worker's `finally` block)
restores the button state regardless of success or failure.

The 200 ms log poll replaces the `time.sleep(1.0)` workaround in the original
notebook entirely, giving near-real-time SCIP progress display with no blocking.

---

## 9. Known issues resolved during conversion

| Issue | Resolution |
|---|---|
| `wgt._options_values` private attribute | Eliminated — entire surrogate mechanism dropped |
| `if/if` bug in `run_oorp` (testmode==4 also runs `oorp`) | Fixed in `_run_worker` with `if/elif/elif/else` |
| `hist_box` read directly in `walk()` and `three_peat()` | Replaced with `p['hist']` via params argument |
| `make_planning_datadict` signature missing `test_mode` / `historical_year_for_rates` | Full signature preserved; all three call patterns mapped explicitly |
| `high_level` module reference in backend | `oorp`, `three_peat`, `walk` are in `solver.py` |
| `get_params_csv()` / `load_params_from_csv()` missing from API | Both added to `Api` class |
| Frontend HTML path relative to cwd | Absolute path via `os.path.abspath(__file__)` in `main.py` |
| `self.window` assignment not shown | Explicit `api.window = window` in `main.py` |
| Historical year dropdown not populated | `get_hist_options()` API call at startup |
| `PARAM_DEFAULTS` wrong for infl/frac/xinc/xinr/spndm | Corrected to use widget percent values |
| Plotly CDN dependency for offline app | Bundled `plotly.min.js` shipped with app |
| `time.sleep(1.0)` flush workaround | Replaced by 200 ms JS poll of `poll_log()` |

---

## 10. What is explicitly not changed

- `oorplp` — the entire SCIP model formulation (lines 1501–2021), all
  constraints, variables, and objective functions. Zero changes.
- All tax tables and bracket logic (`bkts_for_year`, `tax_bucket_n_size`, etc.).
- `historical/rates.csv` format and loading.
- The parameter CSV file format — fully backward compatible with existing
  saved files. The `ps.loc[key]['0']` access pattern is correct as-is.
- The nine chart definitions in `display_dd` — same `px.bar`/`px.line` calls,
  same `color_discrete_map`, same `barmode='relative'`.
- `dd_test_revised.ipynb` — continues to work against the unchanged solver.
- The notebook itself — continues to function in Jupyter independently.

---

## 11. Migration sequence

Each stage leaves the notebook fully functional. The desktop app becomes
runnable at the end of Stage 3 and feature-complete at Stage 5.

### Stage 1 — Extract and test core logic

1. Create `planner.py`: extract lines 22–1401. Replace all `xxx_box.value` with
   `p['xxx']`. Add `warn_cb` injection. Define corrected `PARAM_DEFAULTS`.
   Use `__file__`-relative path for `historical/rates.csv`.
2. Create `solver.py`: extract lines 1404–2580. Add `params` argument to
   `oorp`, `walk`, `walk_lap`, `three_peat`. Replace `hist_box.value` with
   `p['hist']`. Add `warn_cb` injection. Remove all `with out_box:` / `with
   drb_out:` / `err_out.clear_output()` calls. Add return values to `oorp`,
   `walk`, `three_peat`.
3. Write `test_planner.py`: construct a `params_dict` from `PARAM_DEFAULTS`,
   call `make_planning_datadict`, verify `dd` structure. Run `oorplp` via
   `solver.py` and confirm output matches `dd_test_revised.ipynb`.

**Exit criterion:** `python test_planner.py` passes; `dd_test_revised.ipynb`
passes against output produced by `solver.py`.

### Stage 2 — Create renderer

1. Create `renderer.py`: adapt `display_dd` to `render_dd` returning typed
   items. Create `render_three_peat`.
2. Verify Plotly JSON round-trip: the structure returned by `fig.to_json()` is
   directly usable as `Plotly.newPlot(div, fig_obj.data, fig_obj.layout)`.
3. Verify table HTML renders correctly in a browser.

**Exit criterion:** `render_dd(dd)` returns correct items; manual browser test
confirms chart and table appearance.

### Stage 3 — Minimal working desktop app

1. Write `backend.py` with `Api` class (§6), worker thread, log queue,
   all parameter and run-control API methods.
2. Write `main.py` (§4.5), including `api.window = window`.
3. Download and commit `plotly.min.js` to `frontend/`.
4. Write minimal `frontend/index.html` and `app.js` — just enough to confirm
   bridge works: `pywebviewready` handler, `collectParams`, `run_projection`
   call, `renderResults` stub that logs to console.
5. `pip install "pywebview>=5.3"` in the venv.
6. Run `python main.py`, verify solver runs in background without freezing the
   window, SCIP log text appears, results return.

**Exit criterion:** Window opens; Run triggers solver; log populates; basic
results render without error; Run button re-enables on completion or exception.

### Stage 4 — Full form and results UI

1. Build all form sections in `index.html`, matching `winputs` widget layout.
2. Populate `hist` dropdown from `get_hist_options()` in `pywebviewready`.
3. Style with `style.css`.
4. Implement all `app.js` handlers: glide enable/disable, save/load buttons,
   clipboard copy/paste.
5. Implement full `renderResults`: Plotly charts, table HTML, heading elements.
6. Implement `appendWarning` with `textContent` (not `innerHTML`).

**Exit criterion:** All 89 form fields present and correct; save/load round-trip
works; all 9 charts render; tables appear; warnings display; glide enable/disable
works.

### Stage 5 — Polish and venv finalization

1. Update `requirements.txt` as per §3.
2. Test on a fresh venv: `python -m venv .venv && pip install -r requirements.txt`.
3. Test all five testmode values (Normal, Artificial Losses, Alternate Objective,
   3-peat, Random Walk).
4. Confirm parameter CSV round-trip: save from notebook → load in desktop app
   and vice versa.
5. Confirm app launches correctly from directories other than the project root
   (validates `__file__`-relative paths throughout).
6. Fix the `wgt._options_values` → `wgt.options` issue in the notebook as a
   separate notebook-side change.

**Exit criterion:** Both environments produce identical numerical output for the
same parameter file; `requirements.txt` installs cleanly from scratch; app
launches from any working directory.
