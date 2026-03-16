# Makefile for e-ORP — single venv, notebook or desktop
# Copyright (c) 2025 Doug Currie
#
# requirements.txt = shared deps; requirements-notebook.txt / requirements-desktop.txt = add-ons.
# To support both notebook and desktop in one venv: pip install -r requirements-notebook.txt -r requirements-desktop.txt (after venv).

VENV = ORPy-venv
PLOTLY_JS_VERSION = 3.0.1
FRONTEND_PLOTLY = frontend/plotly.min.js

venv: $(VENV)/touchfile

$(VENV)/touchfile: requirements.txt
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt
	touch $(VENV)/touchfile

# Notebook: install notebook add-on and register kernel, then run Jupyter Lab
$(VENV)/notebook-deps: $(VENV)/touchfile requirements-notebook.txt
	$(VENV)/bin/pip install -r requirements-notebook.txt
	$(VENV)/bin/python -m ipykernel install --user --name $(VENV) --display-name "ORPy venv"
	touch $(VENV)/notebook-deps

run: $(VENV)/notebook-deps
	$(VENV)/bin/jupyter-lab

# Desktop: one-time setup (venv + desktop add-on + Plotly.js)
$(VENV)/desktop-deps: $(VENV)/touchfile requirements-desktop.txt
	$(VENV)/bin/pip install -r requirements-desktop.txt
	touch $(VENV)/desktop-deps

$(FRONTEND_PLOTLY):
	curl -fSL -o $(FRONTEND_PLOTLY) https://cdn.plot.ly/plotly-$(PLOTLY_JS_VERSION).min.js

desktop-setup: $(VENV)/desktop-deps $(FRONTEND_PLOTLY)

# Desktop: run the PyWebView app (run from project root)
desktop: desktop-setup
	$(VENV)/bin/python main.py

clean:
	rm -rf $(VENV)
