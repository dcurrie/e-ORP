# Plan: Support Both Jupyter Notebook and PyWebView Desktop

Retain the option to run either the e-ORP Jupyter notebook or the PyWebView desktop app from the same repo, with a single venv and clear Makefile targets.

**Status: Implemented.** See `requirements.txt`, `requirements-notebook.txt`, `requirements-desktop.txt`, and the Makefile.

---

## 1. Goals

- **Notebook:** `make run` starts Jupyter Lab so the user can work with `e-ORP.ipynb` (and other notebooks). Requires: jupyter, ipykernel, ipywidgets, plus shared code deps (pandas, plotly, pyscipopt).
- **Desktop:** `make desktop-setup` prepares the venv and frontend (Plotly.js); `make desktop` runs the PyWebView app (`python main.py`). Requires: pywebview, plus shared deps; no Jupyter.
- One virtualenv should be able to support both workflows so a developer can switch without recreating the env.

---

## 2. Requirements: Separate Files vs Superset

**Can you have separate requirements files?** Yes. Two common patterns:

| Approach | How it works | Pros | Cons |
|----------|----------------|------|------|
| **Superset** | Single `requirements.txt` with every package (notebook + desktop). `pip install -r requirements.txt` once. | One install, both targets work. | Slightly larger install for desktop-only users. |
| **Separate** | e.g. `requirements.txt` (shared + desktop), `requirements-notebook.txt` (jupyter, ipykernel, ipywidgets). Install with `pip install -r requirements.txt -r requirements-notebook.txt` for both. | Desktop-only users install only `requirements.txt`; notebook users add the second file. | Two files to maintain; `make run` must ensure notebook deps are installed. |

**Recommendation:** Use a **superset** in one `requirements.txt` so that a single `make venv` (or `make desktop-setup`) gives an env that supports both `make run` and `make desktop`. Simpler for docs and for anyone who uses both. If you prefer minimal installs, use **separate** files and have the Makefile install notebook deps only when needed (e.g. a `notebook-deps` target that installs `requirements-notebook.txt` and have `run` depend on it).

**Concrete split if separate:**

- **requirements.txt** (shared + desktop): `pandas`, `plotly`, `pyscipopt`, `pywebview`, `openpyxl`. No Jupyter.
- **requirements-notebook.txt** (notebook only): `jupyter`, `jupyterlab` (or `notebook`), `ipykernel`, `ipywidgets`.  
  Then `venv` depends on `requirements.txt`; a target `notebook-deps` installs `requirements-notebook.txt`; `run` depends on `venv` and `notebook-deps` and then runs `jupyter-lab`.

**Concrete superset:**

- **requirements.txt**: current desktop packages plus `jupyter`, `jupyterlab`, `ipykernel`, `ipywidgets`. One file; `venv` and `desktop-setup` use it; both `run` and `desktop` work.

---

## 3. Makefile Changes

| Target | Current behavior | New behavior |
|--------|------------------|--------------|
| **venv** | Create venv, install requirements.txt, register ipykernel. | Unchanged, but ensure requirements.txt includes notebook deps if using superset; if using separate files, venv installs only requirements.txt (desktop deps) and does *not* run ipykernel install (move that to a notebook-setup or run dependency). |
| **run** | `jupyter-lab` | Unchanged: run the notebook (Jupyter Lab). Ensure venv has notebook deps (either via superset in requirements.txt or via a dependency that installs requirements-notebook.txt). |
| **desktop** | venv + download Plotly.js | **Rename to `desktop-setup`.** Same as now: ensure venv exists and `frontend/plotly.min.js` exists. |
| **desktop** (new) | — | **New target:** run the PyWebView app. Example: `$(VENV)/bin/python main.py` (from project root). Must run from e-ORP directory so frontend and CWD are correct; the Makefile can `cd` into the project dir or assume the user runs `make desktop` from the repo root. |

**Suggested Makefile layout:**

```makefile
VENV = ORPy-venv
PLOTLY_JS_VERSION = 3.0.1
FRONTEND_PLOTLY = frontend/plotly.min.js

# Base venv: install requirements (superset or desktop-only depending on choice above)
venv: $(VENV)/touchfile
$(VENV)/touchfile: requirements.txt
	python3 -m venv $(VENV)
	source $(VENV)/bin/activate && pip3 install -r requirements.txt
	# If superset: also register kernel for notebook
	source $(VENV)/bin/activate && python3 -m ipykernel install --user --name $(VENV) --display-name "ORPy venv"
	touch $(VENV)/touchfile

# Notebook: run Jupyter Lab
run: venv
	source $(VENV)/bin/activate && jupyter-lab

# Desktop: one-time setup (venv + Plotly.js)
desktop-setup: venv $(FRONTEND_PLOTLY)
$(FRONTEND_PLOTLY):
	curl -fSL -o $(FRONTEND_PLOTLY) https://cdn.plot.ly/plotly-$(PLOTLY_JS_VERSION).min.js

# Desktop: run the PyWebView app (must be run from project root)
desktop: desktop-setup
	$(VENV)/bin/python main.py

clean:
	rm -rf $(VENV)
```

If using **separate** requirement files, add a target so notebook deps are installed when running the notebook, e.g.:

```makefile
# Optional: install notebook deps so run works (if requirements.txt is desktop-only)
notebook-deps: venv
	source $(VENV)/bin/activate && pip3 install -r requirements-notebook.txt
	source $(VENV)/bin/activate && python3 -m ipykernel install --user --name $(VENV) --display-name "ORPy venv"

run: notebook-deps
	source $(VENV)/bin/activate && jupyter-lab
```

and keep `venv` depending only on `requirements.txt` (no ipykernel install in venv).

---

## 4. Implementation Steps

1. **Decide requirements strategy:** Superset (one requirements.txt) or separate (requirements.txt + requirements-notebook.txt). Add notebook packages to the chosen file(s).
2. **Makefile:**  
   - Rename current `desktop` target to `desktop-setup`.  
   - Add new `desktop` target that depends on `desktop-setup` and runs `$(VENV)/bin/python main.py`.  
   - Keep `run` as-is (jupyter-lab); ensure its dependency (venv or notebook-deps) installs notebook packages and, if applicable, registers the ipykernel.
3. **Docs:** Update DESKTOP.md (and any README) to say: use `make desktop-setup` once to prepare, then `make desktop` to run the app; use `make run` to start Jupyter Lab for the notebook. Mention that both can use the same venv.

---

## 5. Summary

| Question | Answer |
|----------|--------|
| Separate requirements files? | Yes. Use either one superset file or separate (e.g. requirements.txt + requirements-notebook.txt) and have the Makefile install the right set for each target. |
| `run` | Runs the notebook (Jupyter Lab). |
| `desktop-setup` | Current `desktop`: venv + Plotly.js. |
| `desktop` | New: run the PyWebView app (`python main.py`). |
