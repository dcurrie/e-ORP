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


def _load_params(name):
    """Load a params/*.csv the way every front end does."""
    from planner import params_from_csv
    return params_from_csv(os.path.join('params', name))


def test_oorp_short():
    from solver import oorp
    p = dict(PARAM_DEFAULTS)
    dd, r = oorp(p, mode=0, objt=0, test='', tout=5, glim=0.02, fname=None, warn_cb=lambda m: None)
    assert r.status in ('optimal', 'timelimit', 'gaplimit')
    assert r.ok()
    # The diagnostic must not fire (or cost time) on a feasible plan.
    assert r.diagnosis is None
    assert not r.slacks
    assert len(dd['year']) >= 2
    print("test_oorp_short: OK")


def test_elastic_infeasible_residual():
    """The exit criterion the IIS work never met: a real infeasibility, diagnosed.

    params/infeasible.csv asks for a $3M terminal residual against modest balances.
    The measured feasibility frontier is ~2432.6 nominal against a required 5120.66,
    so the residual is short by ~1575 base-year $k. Asserted loosely: the frontier
    moves whenever the tax tables change, but the sign, the lever and the order of
    magnitude are invariants.
    """
    from solver import oorp
    p = _load_params('infeasible.csv')
    dd, r = oorp(p, mode=0, objt=0, test='', tout=5, glim=0.02, fname=None,
                 warn_cb=lambda m: None)
    assert r.status == 'infeasible', r.status
    assert r.diagnosis is not None
    assert r.diagnosis['kind'] == 'elastic', r.diagnosis
    rows = [x for x in r.diagnosis['rows'] if x.get('param') == 'ftab']
    assert len(rows) == 1, r.diagnosis['rows']
    assert rows[0]['shortfall_real'] > 0
    assert 1000.0 < rows[0]['shortfall_real'] < 2500.0, rows[0]
    assert 0.0 < rows[0]['suggested'] < rows[0]['current'], rows[0]
    # current/suggested are in the units the user typed (base-year $), not the
    # final-year nominal target: a regression here once reported 5120.7 -> 3545.0.
    assert rows[0]['current'] == p['ftab'], rows[0]
    assert abs(rows[0]['suggested'] - (p['ftab'] - rows[0]['shortfall_real'])) < 0.2, rows[0]
    print("test_elastic_infeasible_residual: OK")


def test_example_p_solves():
    """Regression guard for the horizon-aware max_tab.

    params/example_p.csv used to be infeasible with nothing wrong with the plan: the
    account cap grew at the rate of inflation while the balances grew at the rate of
    return, so over 27 years the cap fell behind (needed 3280, capped at 1707).
    asset_ceiling() now sizes the cap, and this scenario solves.
    """
    from solver import oorp
    dd, r = oorp(_load_params('example_p.csv'), mode=0, objt=0, test='', tout=20,
                 glim=0.25, fname=None, warn_cb=lambda m: None)
    assert r.ok(), (r.status, r.diagnosis)
    assert r.di > 0
    print("test_example_p_solves: OK")


def test_asset_ceiling_bounds_every_balance():
    """asset_ceiling() must be a genuine upper bound, or the solver's caps cut off
    valid plans -- the failure mode that made example_p.csv infeasible."""
    from planner import asset_ceiling
    from solver import oorp
    p = _load_params('example_p.csv')
    dd, r = oorp(p, mode=0, objt=0, test='', tout=20, glim=0.25, fname=None,
                 warn_cb=lambda m: None)
    assert r.ok()
    ceil = asset_ceiling(dd)
    for y in range(1, len(dd['e'])):
        total = (dd['afterTax'][y] + dd['e_Taxd'][y] + dd['j_Taxd'][y]
                 + dd['e_Roth'][y] + dd['j_Roth'][y])
        assert total <= ceil[y] * 1.000001, (y, total, ceil[y])
    print("test_asset_ceiling_bounds_every_balance: OK")


def test_bounds_probe_names_culprits():
    """The bounds probe must name the cap that was binding, not just report 'bounds'.

    Solving example_p.csv with the caps doubled shows which ones the shipped scale was
    still clipping -- currently the max_xfr-derived transfer caps on from_aTax/to_aTax.
    """
    from planner import make_planning_datadict
    from solver import oorplp
    dd = make_planning_datadict(_load_params('example_p.csv'), warn_cb=lambda m: None)
    r = oorplp(dd, 0, 0, 20, 0.25, bounds_scale=2.0)
    assert r.ok(), r.status
    assert r.bound_culprits, 'expected the doubled run to exceed a shipped cap'
    for c in r.bound_culprits:
        assert c['needed'] > c['capped_at'], c
    print(f"test_bounds_probe_names_culprits: OK "
          f"({sorted({c['var'] for c in r.bound_culprits})})")


def test_elastic_mixed_options():
    """Residual and spending shortfalls are alternatives, reported as separate options.

    infeasible.csv with a smaller Plan Surplus and $60k/yr of essential spending can be
    fixed by either lever alone. They used to share one table, which read as additive,
    showed NaN in the spending rows' Current/Suggested, and kept only the ten largest
    rows, so some affected years silently went missing.
    """
    from renderer import render_diagnosis
    from solver import oorp
    p = _load_params('infeasible.csv')
    p.update({'ftab': 1200.0, 'yr01': p['byear'] + 1, 'pr01': 1, 'va01': 60.0})
    dd, r = oorp(p, mode=0, objt=0, test='', tout=5, glim=0.25, fname=None,
                 warn_cb=lambda m: None)
    d = r.diagnosis
    assert d['kind'] == 'elastic', d
    opts = d['options']
    assert [o['lever'] for o in opts] == ['Minimum residual (Plan Surplus)',
                                          'Essential spending'], opts
    assert d['headline'].startswith('Either '), d['headline']
    spend = opts[1]['rows']
    assert [x['year'] for x in spend] == sorted(x['year'] for x in spend)
    for x in spend:
        # base-year $, the units the user entered, and never cut below zero
        assert abs(x['current'] - 60.0) < 0.2, x
        assert abs(x['suggested'] - max(0.0, x['current'] - x['shortfall_real'])) < 0.2, x
    assert abs(opts[1]['total_real'] - sum(x['shortfall_real'] for x in spend)) < 0.01
    assert len(d['rows']) == 1 + len(spend), 'rows must not be truncated'
    items = render_diagnosis(d)
    tables = [i for i in items if i['type'] == 'table']
    assert len(tables) == 2
    assert not any('NaN' in t['html'] for t in tables)
    assert any(i['type'] == 'note' and i['text'].startswith('Option 2') for i in items)
    print(f"test_elastic_mixed_options: OK ({len(spend)} spending years)")


def test_diagnosis_blames_mode_not_bounds():
    """A plan that fails only under the user's mode must not be reported as a bounds bug.

    The probes run at mode 0, which drops basis averaging. Calling the diagnosis
    directly on a plan that solves at mode 0 stands in for one that fails at mode 1/4
    but not at mode 0: before the mode baseline, the 4x bounds probe solved and the
    user was told e-ORP had a bug.
    """
    from solver import diagnose_infeasible
    p = dict(PARAM_DEFAULTS)
    for mode in (1, 4):
        d = diagnose_infeasible(p, mode, 0, '', 5)
        assert d['kind'] == 'mode', (mode, d)
        assert 'Normal (fastest)' in d['headline'], d
    # Mode 0 cannot be looser than mode 2, and modes 0 and 3 are identical, so none
    # of these may take the mode branch.
    for mode in (0, 2, 3):
        assert diagnose_infeasible(p, mode, 0, '', 5)['kind'] != 'mode', mode
    print("test_diagnosis_blames_mode_not_bounds: OK")


def test_render_diagnosis():
    from renderer import render_diagnosis
    diag = {
        'kind': 'elastic',
        'headline': 'Minimum residual is about $1,575k (base-year $) too high.',
        'rows': [{'lever': 'Minimum residual (Plan Surplus)', 'year': 2051,
                  'shortfall_real': 1574.9, 'shortfall_nominal': 2688.1,
                  'param': 'ftab', 'current': 3000.0, 'suggested': 1425.1}],
        'notes': ['Model upper bounds were checked and are not the cause.'],
        'approximate': False,
    }
    items = render_diagnosis(diag)
    assert items[0]['type'] == 'heading'
    assert items[1]['type'] == 'note' and '1,575' in items[1]['text']
    table = [i for i in items if i['type'] == 'table']
    assert len(table) == 1
    assert 'orp-table' in table[0]['html'] and '1425.1' in table[0]['html']
    assert any(i['type'] == 'note' and 'upper bounds' in i['text'] for i in items)
    # An empty diagnosis must still render something rather than vanish.
    assert render_diagnosis(None)[1]['type'] == 'note'
    print("test_render_diagnosis: OK")


def _modern(path):
    """params/*.csv written in the current schema; legacy files load as mostly-defaults."""
    import pandas as pd
    ps = pd.read_csv(path, index_col=0, keep_default_na=False)
    try:
        return 'fage1' in ps.index and float(ps.loc['rors', ps.columns[0]]) >= 1.0
    except (KeyError, TypeError, ValueError):
        return False


def test_triage_no_false_positives():
    """A triage warning on a plan the solver can actually handle is worse than none."""
    import glob
    from planner import triage_feasibility
    checked = 0
    for path in sorted(glob.glob(os.path.join('params', '*.csv'))):
        if not _modern(path):
            continue
        dd = make_planning_datadict(_load_params(os.path.basename(path)),
                                    warn_cb=lambda m: None)
        msgs, _w, _req = triage_feasibility(dd)
        assert not [m for m in msgs if 'cannot work' in m], (path, msgs)
        checked += 1
    assert checked >= 3, f'only {checked} modern scenarios found'
    print(f"test_triage_no_false_positives: OK ({checked} scenarios)")


def test_triage_catches_impossible_spending():
    """Essential spending that outruns every account must be caught before SCIP runs."""
    from planner import triage_feasibility
    p = dict(PARAM_DEFAULTS)
    # 'Ongoing Essential Spending Set To:' $900k/yr against $320k of total balances.
    p.update({'yr01': p['byear'] + 1, 'pr01': 1, 'va01': 900.0})
    warns = []
    dd = make_planning_datadict(p, warn_cb=warns.append)
    msgs, _w, _req = triage_feasibility(dd)
    assert any('cannot work' in m for m in msgs), msgs
    # and it must reach the caller through the existing warning channel
    assert any('cannot work' in w for w in warns), warns
    print("test_triage_catches_impossible_spending: OK")


def test_triage_advisory_on_infeasible():
    """params/infeasible.csv is infeasible for reasons arithmetic cannot prove, but
    its final-balance headroom is thin enough to warn about."""
    from planner import triage_feasibility
    dd = make_planning_datadict(_load_params('infeasible.csv'), warn_cb=lambda m: None)
    msgs, w, req = triage_feasibility(dd)
    assert any('headroom' in m for m in msgs), (msgs, w, req)
    assert w > req, 'ceiling must stay a genuine upper bound'
    print("test_triage_advisory_on_infeasible: OK")


if __name__ == '__main__':
    test_make_planning_datadict()
    test_oorp_short()
    test_elastic_infeasible_residual()
    test_example_p_solves()
    test_asset_ceiling_bounds_every_balance()
    test_bounds_probe_names_culprits()
    test_elastic_mixed_options()
    test_diagnosis_blames_mode_not_bounds()
    test_render_diagnosis()
    test_triage_no_false_positives()
    test_triage_catches_impossible_spending()
    test_triage_advisory_on_infeasible()
    print("All tests passed.")
