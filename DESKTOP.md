# e-ORP Desktop App (PyWebView)

Run the desktop app from the **project directory** so the built-in HTTP server can serve the frontend and the JS↔Python bridge works:

```bash
cd /path/to/e-ORP
./ORPy-venv/bin/python main.py
```

Or with your own venv:

```bash
cd /path/to/e-ORP
python main.py
```

## Requirements

- Python 3 with packages in `requirements.txt`: `pandas`, `plotly`, `pyscipopt`, `pywebview`
- **Plotly.js** (frontend): `frontend/plotly.min.js` is not in the repo. Use **tested version 3.0.1**. Either run `make desktop` (see below) to fetch it, or download manually:
  - Minified: https://cdn.plot.ly/plotly-3.0.1.min.js → save as `frontend/plotly.min.js`
  - Or from GitHub: https://github.com/plotly/plotly.js/releases/tag/v3.0.1

To set up everything (venv + Plotly.js): from the project root run `make desktop`. Or create venv and fetch Plotly.js yourself: `python -m venv ORPy-venv && ORPy-venv/bin/pip install -r requirements.txt`, then download `plotly-3.0.1.min.js` to `frontend/plotly.min.js`.

## Debug mode

To open developer tools (e.g. to inspect the WebView console):

```bash
python main.py --debug
```

## macOS (Cocoa)

On macOS, pywebview uses the Cocoa/WebKit backend. The bridge exposes Python API methods in **snake_case** (e.g. `set_params`, `run_projection`). There is a known issue where the bridge’s internal `pywebview.stringify` is not available in the WebKit context; the app works around this by replacing the Cocoa branch of `_jsApiCallback` so it uses `window.pywebview.stringify` or `JSON.stringify` (see comment in `frontend/index.html` and `frontend/app.js`).

## Quick verification (Load / Run / Save)

After starting the app:

1. **Load** — In “Parameter Save & Load”, set file path to `params/_2025_2.csv` (or any `params/*.csv`), click **Load**. Form fields should update.
2. **Run** — Click **Run Projection**. Button should show “Running…”, SCIP log should fill, then results and charts appear; button returns to “Run Projection”.
3. **Save** — Set file path to e.g. `params/test_save.csv`, click **Save**. File should be created under the project directory.
4. **Copy / Paste** — Click **Copy params**, then paste into the text area and click **Paste params**; form should match the copied state.

## Running the test suite

From the project root with your venv activated:

```bash
./ORPy-venv/bin/python test/run_tests.py
```

Or run each module separately:

```bash
./ORPy-venv/bin/python test/test_planner.py
./ORPy-venv/bin/python test/test_backend.py
```

- **test_planner.py** — planner datadict and a short solver run (oorp).
- **test_backend.py** — API param CSV round-trip (clipboard, file, and relative path like `params/file.csv`).

All tests should pass; the solver test may take a few seconds.
