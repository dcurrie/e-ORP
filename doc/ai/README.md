# README file for AI assistants

This directory has the project context for AI assistants.

Prefer the user's vault context for general preferences and behavior.

This repo's context overrides for project-specific decisions and structure.

The e-ORP project is summarized for human users in the README and DESKTOP files in the project root.

There are two e-ORP versions: notebook and desktop. 
They are intended to produce identical results. 
The project is used to build both. 
Both versions may be used locally. I usually use a Safari browser.
The notebook version and repo structure are maintained so that it can be launched in Binder for non-developer use.

## Build

The project uses a Makefile with targets `desktop` for e-ORP desktop and `notebook` for e-ORP on Jupyter.
The Makefile creates and uses a venv called `ORPy-venv`. 

## Tools

- macOS
- make
- python (v3.9.6)
- pyenv

## Libraries

- PySCIPopt and indirectly SCIP
- pandas
- plotly
- pywebview -- for desktop version only
- jupyter, jupyterlab, ipykernel, ipywidgets -- for notebook version only

See requirements.txt requirements-desktop.txt and requirements-notebook.txt for pinned versions.

## Testing

Ad hoc testing code is in the testing/ directory. It uses a mix of Python with CLI and Python in Jupyter,
the latter for simple GUI and graphics presentation.

## Structure of this project context

Use doc/ai/plans/ for planning documents, and subdirectories for implemented and rejected plans

Use doc/ai/research/ for research findings

Use doc/ai/conventions for guidelines, and notable decisions
