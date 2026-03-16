#!/usr/bin/env python3
"""Basic tests for planner and solver (R3 extraction). Run from repo root with venv."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from planner import make_planning_datadict, PARAM_DEFAULTS


def test_make_planning_datadict():
    p = dict(PARAM_DEFAULTS)
    warnings = []
    dd = make_planning_datadict(p, warn_cb=warnings.append)
    assert 'year' in dd
    assert len(dd['year']) >= 2
    assert dd['year'][0] == p['byear']
    assert 'disp_income' in dd
    assert 'e_Taxd' in dd
    print("test_make_planning_datadict: OK")


def test_oorp_short():
    from solver import oorp
    p = dict(PARAM_DEFAULTS)
    result = oorp(p, mode=0, objt=0, test='', tout=5, glim=0.02, fname=None, warn_cb=lambda m: None)
    dd, status, net_pretax, di, stage, gap, stime = result
    assert status in ('optimal', 'timelimit', 'gaplimit')
    assert len(dd['year']) >= 2
    print("test_oorp_short: OK")


if __name__ == '__main__':
    test_make_planning_datadict()
    test_oorp_short()
    print("All tests passed.")
