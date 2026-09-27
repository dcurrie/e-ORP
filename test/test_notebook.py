#!/usr/bin/env python3
"""Guard e-ORP.ipynb against re-growing its own copy of the model.

The notebook used to inline ~1760 lines duplicating planner.py / solver.py /
renderer.py. That duplication silently accumulated three defects nobody noticed:
the marginal-bracket ladder lost its 35% and 37% rungs (which also corrupted
net_postax), Walk mode ran a second projection after its ten laps, and the
parameter default table drifted from PARAM_DEFAULTS for 17 keys.

These tests are cheap and run without a Jupyter kernel. The widget-level check
needs ipywidgets, which only the notebook venv has, so it skips when absent.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from planner import PARAM_DEFAULTS

NB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  'e-ORP.ipynb')


def _code_cell():
    nb = json.load(open(NB))
    cells = [c for c in nb['cells'] if c['cell_type'] == 'code']
    assert len(cells) == 1, f'expected one code cell, found {len(cells)}'
    return ''.join(cells[0]['source'])


def test_notebook_has_no_model_code():
    """The model must come from the shared modules, not a copy in the notebook."""
    src = _code_cell()
    for banned in ('def oorplp(', 'def make_planning_datadict(', 'def lop_to_cents(',
                   'def walk_lap(', 'def three_peat(', 'import pyscipopt',
                   'tax_rates =', 'tax_brk_2025', 'def IRMAA_buk_n_size('):
        assert banned not in src, f'model code is back in the notebook: {banned!r}'
    for needed in ('from planner import', 'from solver import', 'from renderer import'):
        assert needed in src, f'notebook no longer imports the shared model: {needed!r}'
    print("test_notebook_has_no_model_code: OK")


def test_notebook_compiles():
    compile(_code_cell(), 'e-ORP.ipynb', 'exec')
    print("test_notebook_compiles: OK")


def test_notebook_run_handler_dispatches_once():
    """Walk mode used to fall through and run an ordinary projection as well."""
    src = _code_cell()
    assert 'elif testmode.value == 3:' in src, 'run_oorp must use elif, not a bare if'
    assert src.count('testmode.value == 4') == 1
    print("test_notebook_run_handler_dispatches_once: OK")


def test_notebook_params_table_matches_defaults():
    """One source of truth for parameter defaults.

    The notebook's params table pairs each key with its widget and nothing else; the
    defaults come from PARAM_DEFAULTS. A third column here would be a second source
    of truth, which is exactly what drifted before.
    """
    import re
    src = _code_cell()
    blk = src[src.index('params = ['):]
    blk = blk[:blk.index('\n]')]
    rows = re.findall(r"\[\s*'(\w+)'\s*,\s*(\w+)\s*(,[^\]]*)?\]", blk)
    keys = [r[0] for r in rows]
    extra = [r[0] for r in rows if r[2]]
    assert not extra, f'params table carries its own defaults again: {extra[:5]}'
    assert set(keys) == set(PARAM_DEFAULTS), (
        f'only in notebook: {sorted(set(keys) - set(PARAM_DEFAULTS))}; '
        f'only in PARAM_DEFAULTS: {sorted(set(PARAM_DEFAULTS) - set(keys))}')
    print(f"test_notebook_params_table_matches_defaults: OK ({len(keys)} keys)")


def test_notebook_collect_params_round_trip():
    """Load a params file through the notebook's own widgets and check the dict it
    hands the model matches what every other front end would build."""
    try:
        import ipywidgets  # noqa: F401
    except ImportError:
        print("test_notebook_collect_params_round_trip: SKIPPED (no ipywidgets; "
              "run under the notebook venv)")
        return
    from planner import params_from_csv
    src = _code_cell()
    src = src[:src.rindex('display(widgets.VBox([winputs,')]
    ns = {'__name__': 'nb_under_test'}
    exec(compile(src, 'e-ORP.ipynb', 'exec'), ns)
    for name in ('_2025_2.csv', 'example_l.csv'):
        path = os.path.join('params', name)
        if not os.path.isfile(path):
            continue
        ns['pfname'].value = path
        ns['load_params']()
        got, want = ns['collect_params'](), params_from_csv(path)
        bad = {k: (got.get(k), want[k]) for k in want if got.get(k) != want[k]}
        assert not bad, (name, bad)
    print("test_notebook_collect_params_round_trip: OK")


if __name__ == '__main__':
    test_notebook_compiles()
    test_notebook_has_no_model_code()
    test_notebook_run_handler_dispatches_once()
    test_notebook_params_table_matches_defaults()
    test_notebook_collect_params_round_trip()
    print("All notebook tests passed.")
