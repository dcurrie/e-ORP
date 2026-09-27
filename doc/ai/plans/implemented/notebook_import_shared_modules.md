# e-ORP: Jupyter notebook imports shared `planner` / `solver`

**Status:** Implemented (2026-09-26, branch `elastic-infeasibility-diagnostics`).

The notebook's code cell went from 2630 lines to 1004: ~1626 lines of duplicated model
code deleted, the widget UI kept. It now imports `planner` / `solver` / `renderer`, so
there is one model and the two front ends cannot drift.

**What the duplication had already cost.** Three defects were found in the copy, none of
them in the desktop code:

1. The marginal-bracket ladder was missing its 0.37 and 0.35 rungs, so anyone in the top
   two brackets got a wrong `tax_bracket` — and `net_postax`, computed as
   `(1 - tax_bracket) * (e_Taxd + j_Taxd)`, was overstated with it.
2. `run_oorp` used `if testmode == 4: walk(...)` followed by `if testmode == 3: ... else:
   ...`, with no `elif`, so Walk mode ran its ten laps *and then* an ordinary projection.
3. The `params` table carried its own default column, which had drifted from
   `PARAM_DEFAULTS` for **17 keys** — the allocation fractions and inflation were off by
   100x, `xinc`/`xinr` held a year. It bit whenever a params file omitted those keys,
   which `example_l.csv` and `example_p.csv` do.

**Why it was cheaper than this plan assumed.** The widget->model boundary already
existed: the notebook's `params` table pairs every key with its widget and its key set
is *exactly* `PARAM_DEFAULTS` (89/89), and `save_params` already built the dict the
shared modules take. The two `make_planning_datadict` implementations produced
byte-identical datadicts, and the two `oorplp` implementations were 99.3% identical.
So the port was mechanical, not a redesign.

**What was added:** a bootstrap cell (below), `collect_params()`, `renderer.display_items()`
for drawing the shared item list in Jupyter, and `planner.coerce_param` /
`planner.params_from_csv` so the notebook never has to import `backend` (which pulls in
pywebview). `test/test_notebook.py` guards against the duplication returning.

**Verified:** loading each of `params/_2025_2.csv`, `example_l.csv`, `example_p.csv` and
`infeasible.csv` through the notebook's own Load button yields a params dict identical
to `params_from_csv`, and the resulting projections match the old notebook exactly —
except `example_p.csv`, which the old notebook reported as infeasible and which now
solves (see the `max_tab` fix in `elastic_infeasibility_diagnostics.md`).

## Goal

Use the same Python modules as the desktop app (`planner.py`, `solver.py`) from `e-ORP.ipynb` instead of maintaining duplicate model code in the notebook. This keeps notebook and desktop behavior aligned (including future work such as named constraints and `generateIIS()` for infeasibility).

## Context

- The repo is **not** an installable package today (no `pyproject.toml` / `setup.py`).
- `make run` starts Jupyter Lab from the **project root**; the kernel’s working directory is usually that root.
- Related: [minlp_infeasibility_relaxation_plan.md](minlp_infeasibility_relaxation_plan.md) (solver changes); PySCIPopt 6.x works the same from Jupyter as from desktop.

## Recommended approach (first notebook cell)

Before any `from planner import …`:

```python
import sys
from pathlib import Path

REPO = Path.cwd().resolve()
if not (REPO / "planner.py").exists():
    raise RuntimeError(
        "Start Jupyter from the e-ORP repo root (e.g. `make run` from the directory that contains planner.py)."
    )
sys.path.insert(0, str(REPO))

from planner import make_planning_datadict, PARAM_DEFAULTS
from solver import oorp, oorplp  # import only what the notebook needs
```

Then call `oorp`, `oorplp`, etc., as in `test/test_planner.py`.

## If the kernel cwd is not the repo root

- Prefer starting Jupyter from the repo root (`make run` from `e-ORP/`).
- Or use `%cd /path/to/e-ORP` in a cell before the snippet above.
- Or set `REPO = Path("/absolute/path/to/e-ORP")` (not portable).

## Optional future improvement

Add a minimal `pyproject.toml` and `pip install -e .` so notebooks can `import planner` without `sys.path` manipulation.

## Binder

Use the same pattern if the Binder image’s working directory is the repo root; or add editable install in the Binder build.

## Implementation work (when resumed)

1. Add the bootstrap cell (or equivalent) near the top of `e-ORP.ipynb`.
2. Replace or thin the large inlined code cell so UI/widgets call into `planner` / `solver` instead of duplicating logic.
3. Regression: run one projection in the notebook and compare to desktop or `test/test_planner.py` for the same params.

## References

- `test/test_planner.py` — same import pattern via `sys.path.insert` relative to repo root.
- `Makefile` — `run` target uses `ORPy-venv` and `jupyter-lab` from project root.
- `doc/ai/README.md` — § Build (`desktop`, `notebook`, `ORPy-venv`).
