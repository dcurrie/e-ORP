# Makefile for e-ORP to create and manage venv
# Copyright (c) 2025 Doug Currie

VENV = ORPy-venv
PLOTLY_JS_VERSION = 3.0.1
FRONTEND_PLOTLY = frontend/plotly.min.js

venv: $(VENV)/touchfile

$(VENV)/touchfile: requirements.txt
	python3 -m venv $(VENV)
	source $(VENV)/bin/activate && pip3 install -r requirements.txt \
		&& python3 -m ipykernel install --user --name $(VENV) --display-name "ORPy venv"
	touch $(VENV)/touchfile

# Desktop app: venv + frontend deps (Plotly.js at tested version). Run once to set up.
desktop: venv $(FRONTEND_PLOTLY)

$(FRONTEND_PLOTLY):
	curl -fSL -o $(FRONTEND_PLOTLY) https://cdn.plot.ly/plotly-$(PLOTLY_JS_VERSION).min.js

clean:
	rm -rf $(VENV)

run: venv
	source $(VENV)/bin/activate && jupyter-lab

