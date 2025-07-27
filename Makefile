# Makefile for e-ORP to create and manage venv
# Copyright (c) 2025 Doug Currie

VENV = ORPy-venv

venv: $(VENV)/touchfile

$(VENV)/touchfile: requirements.txt
	python3 -m venv $(VENV)
	source $(VENV)/bin/activate && pip3 install -r requirements.txt \
		&& python3 -m ipykernel install --user --name $(VENV) --display-name "ORPy venv"
	touch $(VENV)/touchfile

clean:
	rm -rf $(VENV)

run: venv
	source $(VENV)/bin/activate && jupyter-lab

