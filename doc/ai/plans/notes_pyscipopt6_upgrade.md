# Note: Upgrading PySCIPopt to 6.x (GitHub / PyPI latest)

e-ORP’s **`requirements.txt`** uses **`pyscipopt>=6,<7`** (PySCIPOpt 6.x / SCIP 10). The latest release line is **PySCIPOpt 6.1.0** (Feb 2025), which bundles **SCIP 10** and adds a native **IIS API** plus performance and bugfixes. This note summarizes advantages and disadvantages of that upgrade.

**Status (2026-03):** Upgrade validated: planner/solver tests, backend/frontend tests, and desktop runs pass. Use the Makefile: targets **`desktop`** and **`notebook`** create and use **`ORPy-venv`** (see `doc/ai/README.md` § Build).

## Advantages of upgrading to 6.x

| Benefit | Detail |
|--------|--------|
| **Native IIS in Python** | `model.generateIIS()` returns an IIS object; get conflicting constraints via `iis.getSubscip().getConss()` and `cons.name`. No subprocess, no writing .lp/.iis files, no parsing. Simplifies and hardens the infeasibility-diagnostics plan (Phase 2). |
| **SCIP 10 performance** | ~4% faster on MILPs, up to ~10% on harder instances; ~9% faster on MINLPs. Better presolving and conflict analysis. |
| **Bugfixes relevant to infeasible runs** | 6.1.0 fixes “getSolTime on infeasible model” segfault and “potentially outdated value of getVal” (#993). Reduces risk of crashes or wrong values when status is infeasible or at time limit. |
| **Other 6.x improvements** | Exact solving mode, `writeStatisticsJson`, expression/matrix performance, type stubs, presolver plugin API. May be useful later. |

## Disadvantages / risks

| Risk | Mitigation |
|------|------------|
| **New bugs** | 6.x is newer; less field exposure than 5.5. Any upgrade can introduce regressions. Mitigate: run the existing test flow and a few manual desktop runs before committing to 6.x. |
| **API or behavior changes** | 5.5 → 6.0 is a major version jump (SCIP 9 → 10). Deprecations or subtle changes in `getVal`/`getObjVal`/params are possible. Mitigate: after `pip install pyscipopt>=6`, run the full solver path (e.g. one optimal and one infeasible scenario) and compare results. |
| **Build / install** | 6.x ships with SCIP 10; wheels on PyPI for macOS (x86_64 and arm64, newer OS versions). If you use a custom SCIP build or an older OS, you may need to build from source. Mitigate: `make desktop` or `make notebook` (uses **ORPy-venv**); or `pip install -r requirements.txt` in a local venv. |

## Recommendation

- **For the infeasibility plan:** Upgrading to **6.x is worthwhile** if the install is smooth on your machine. It removes the Phase 2 workaround (write → SCIP binary → parse) and gives direct access to conflicting constraint names via `generateIIS()`.
- **Procedure (done):** Bump `requirements.txt` to `pyscipopt>=6,<7`, refresh **ORPy-venv** via `make desktop` / `make notebook`, run `test/test_planner.py`, desktop tests, and a manual run. **Next for the infeasibility plan:** implement Phase 2 with `model.generateIIS()` (no subprocess workaround).

## References

- PySCIPOpt releases: https://github.com/scipopt/PySCIPOpt/releases (v6.0.0, v6.1.0)
- IIS tutorial (6.x): https://pyscipopt.readthedocs.io/en/latest/tutorials/iis.html
- SCIP 10 release: https://www.scipopt.org/ (IIS integrated in SCIP 10)
