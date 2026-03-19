# e-ORP: Jupyter notebook imports shared `planner` / `solver`

**Status:** Deferred — record the approach; implementation set aside for now.

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
