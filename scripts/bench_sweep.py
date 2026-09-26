#!/usr/bin/env python3
"""Benchmark sweep for e-ORP: scenarios x gap limit x mode -> a tidy CSV.

The question this answers is "how much objective value do I give up for how much
speed", so the shipped gap-limit and timeout defaults can be chosen from evidence
instead of from habit.

Run from the repo root:

    ./ORPy-venv/bin/python scripts/bench_sweep.py --quick
    ./ORPy-venv/bin/python scripts/bench_sweep.py \
        --params-dir params --params-dir /Volumes/evo2Te/dev/e-ORP/params
    ./ORPy-venv/bin/python scripts/bench_sweep.py --bounds
    ./ORPy-venv/bin/python scripts/bench_sweep.py --summary data/_bench_20260926.csv

Scenario files are read in place; nothing is copied into this repo.

Timeout is deliberately NOT swept. It is a censoring threshold, not an independent
factor -- a run at tout=120 is the tout=60 run continued -- so sweeping it multiplies
cost for information already in the scip_time_s column.
"""
import argparse
import datetime as _dt
import glob
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from planner import make_planning_datadict, PARAM_DEFAULTS, params_from_csv
from solver import oorplp

GLIMS = [0.0, 0.25, 0.5, 1.0]
MODES = [0, 4]
TOUT = 60.0
OBJT = 0                    # maximize spend: the objective the answer is about
BOUND_SCALES = [1.0, 2.0, 4.0]

COLUMNS = [
    'run_ts', 'scenario', 'params_path', 'mode', 'objective', 'tout_s', 'glim_pct',
    'bound_scale', 'status', 'stage', 'has_solution', 'gap_pct', 'scip_time_s',
    'model_build_s', 'build_dd_s', 'total_wall_s', 'net_pretax', 'di_year1',
    'plan_years', 'n_warnings', 'git_branch', 'host',
]

def load_params(path):
    return params_from_csv(path)


def is_modern(path):
    """Legacy files lack fage1 and carry rates as fractions (rors,0.07 meaning 7%).

    load_params only copies keys present in PARAM_DEFAULTS, so a legacy file loads as
    mostly-defaults with a 0.07% return and solves happily to meaningless numbers.
    """
    try:
        ps = pd.read_csv(path, index_col=0, keep_default_na=False)
        return 'fage1' in ps.index and float(ps.loc['rors', ps.columns[0]]) >= 1.0
    except Exception:
        return False


class _Quiet:
    """Silence SCIP at the file-descriptor level; it prints from C, so
    contextlib.redirect_stdout does not catch it."""

    def __enter__(self):
        sys.stdout.flush()
        self._devnull = os.open(os.devnull, os.O_WRONLY)
        self._saved = os.dup(1)
        os.dup2(self._devnull, 1)
        return self

    def __exit__(self, *exc):
        sys.stdout.flush()
        os.dup2(self._saved, 1)
        os.close(self._saved)
        os.close(self._devnull)
        return False


def _git_branch():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ''


def one_run(path, mode, glim, tout, bound_scale, run_ts, branch, host, quiet=True):
    p = load_params(path)
    warns = []
    t0 = time.perf_counter()
    dd = make_planning_datadict(p, warn_cb=warns.append, objective=OBJT)
    t1 = time.perf_counter()
    ctx = _Quiet() if quiet else _DummyCtx()
    with ctx:
        r = oorplp(dd, mode, OBJT, tout, glim, bounds_scale=bound_scale)
    t2 = time.perf_counter()
    return {
        'run_ts': run_ts,
        'scenario': os.path.basename(path),
        'params_path': path,
        'mode': mode,
        'objective': OBJT,
        'tout_s': tout,
        'glim_pct': glim,
        'bound_scale': bound_scale,
        'status': r.status,
        'stage': r.stage,
        'has_solution': r.has_solution,
        'gap_pct': (100.0 * r.gap) if r.gap < 1e17 else float('inf'),
        'scip_time_s': round(r.stime, 3),
        'model_build_s': round((t2 - t1) - r.stime, 3),
        'build_dd_s': round(t1 - t0, 3),
        'total_wall_s': round(t2 - t0, 3),
        'net_pretax': r.net_pretax if r.has_solution else None,
        'di_year1': r.di if r.has_solution else None,
        'plan_years': len(dd['e']) - 1,
        'n_warnings': len(warns),
        'git_branch': branch,
        'host': host,
    }


class _DummyCtx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def collect(paths, modes, glims, tout, bound_scales, out_path, quiet=True):
    run_ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    branch, host = _git_branch(), socket.gethostname()
    total = len(paths) * len(modes) * len(glims) * len(bound_scales)
    rows, i, started = [], 0, time.perf_counter()
    for path in paths:
        for mode in modes:
            for glim in glims:
                for bs in bound_scales:
                    i += 1
                    label = (f'[{i}/{total}] {os.path.basename(path)} '
                             f'mode={mode} glim={glim} bs={bs}')
                    print(label + ' ...', end='', flush=True)
                    try:
                        row = one_run(path, mode, glim, tout, bs, run_ts,
                                      branch, host, quiet=quiet)
                    except Exception as e:      # one bad scenario must not lose the sweep
                        print(f' ERROR {type(e).__name__}: {e}', flush=True)
                        continue
                    rows.append(row)
                    print(f" {row['status']:>10s} {row['total_wall_s']:7.2f}s "
                          f"DI={row['di_year1'] if row['di_year1'] is not None else float('nan'):.3f}",
                          flush=True)
                    pd.DataFrame(rows, columns=COLUMNS).to_csv(out_path, index=False)
    print(f'\n{len(rows)} runs in {time.perf_counter() - started:.1f}s -> {out_path}')
    return pd.DataFrame(rows, columns=COLUMNS)


def summarize(df, tol):
    """Two tables and one decision line."""
    df = df[df['bound_scale'] == 1.0]
    if df.empty:
        print('No bound_scale=1.0 rows to summarize.')
        return

    base = {}
    for (scen, mode), g in df.groupby(['scenario', 'mode']):
        z = g[g['glim_pct'] == 0.0]
        if len(z) and bool(z.iloc[0]['has_solution']):
            base[(scen, mode)] = float(z.iloc[0]['di_year1'])

    print('\n== Table 1: speed / quality per scenario ==')
    print(f"{'scenario':24s} {'mode':>4s} {'glim':>5s} {'wall_s':>8s} "
          f"{'DI_year1':>10s} {'dDI_vs_0':>10s} {'speedup':>8s}")
    rows = []
    for _, r in df.sort_values(['scenario', 'mode', 'glim_pct']).iterrows():
        key = (r['scenario'], r['mode'])
        b = base.get(key)
        if b and r['has_solution'] and b != 0:
            d = 100.0 * (float(r['di_year1']) - b) / b
            ds = f'{d:+.3f}%'
        else:
            d, ds = None, 'n/a'
        z = df[(df['scenario'] == r['scenario']) & (df['mode'] == r['mode'])
               & (df['glim_pct'] == 0.0)]
        sp = (float(z.iloc[0]['total_wall_s']) / r['total_wall_s']) if len(z) and r['total_wall_s'] else None
        print(f"{r['scenario']:24s} {r['mode']:>4d} {r['glim_pct']:>5.2f} "
              f"{r['total_wall_s']:>8.2f} "
              f"{(float(r['di_year1']) if r['di_year1'] is not None else float('nan')):>10.3f} "
              f"{ds:>10s} {(f'{sp:.1f}x' if sp else '-'):>8s}")
        rows.append({'glim': r['glim_pct'], 'd': d, 'wall': r['total_wall_s'],
                     'status': r['status'], 'has': bool(r['has_solution'])})

    agg = pd.DataFrame(rows)
    print('\n== Table 2: aggregate per gap limit ==')
    print(f"{'glim':>5s} {'worst_dDI':>10s} {'median_dDI':>11s} {'total_wall':>11s} "
          f"{'worst_wall':>11s} {'n_timelimit':>12s} {'n_no_soln':>10s}")
    summary = {}
    for glim, g in agg.groupby('glim'):
        dd_ = g['d'].dropna()
        worst = dd_.min() if len(dd_) else 0.0
        summary[glim] = (worst, g['wall'].sum())
        print(f"{glim:>5.2f} {worst:>9.3f}% {(dd_.median() if len(dd_) else 0.0):>10.3f}% "
              f"{g['wall'].sum():>11.1f} {g['wall'].max():>11.2f} "
              f"{int((g['status'] == 'timelimit').sum()):>12d} "
              f"{int((~g['has']).sum()):>10d}")

    ok = [gl for gl, (w, _t) in sorted(summary.items()) if abs(w) <= tol]
    print()
    if ok:
        pick = min(ok[1:]) if len(ok) > 1 else ok[0]
        w, t = summary[pick]
        b = summary.get(0.0, (0.0, t))[1]
        print(f'RECOMMENDATION: within a {tol:.2f}% tolerance, gap limit {pick:g} '
              f'costs at worst {abs(w):.3f}% of objective and cuts total sweep time '
              f'from {b:.1f}s to {t:.1f}s ({(b / t if t else 1):.1f}x).')
    else:
        print(f'RECOMMENDATION: no gap limit stays within {tol:.2f}%; keep 0.')
    m0 = df[(df['mode'] == 0) & (df['glim_pct'] > 0) & (df['has_solution'])]
    if len(m0):
        print(f'                mode 0 scip_time max at glim>0 is '
              f'{m0["scip_time_s"].max():.1f}s -> a {max(10, int(m0["scip_time_s"].max() * 4)):d}s '
              f'timeout is ample for the fast first pass.')
    nb = df[(df['mode'] == 4) & (~df['has_solution'])]
    if len(nb):
        print(f'                mode 4 found no incumbent in {len(nb)} run(s) at '
              f'tout={TOUT:g}s -- keep the timeout generous for the nuanced modes.')


def report_bounds(df):
    """Flag scenarios whose infeasibility is caused by e-ORP's own variable bounds."""
    print('\n== Bounds sensitivity ==')
    flips, quality = [], []
    for (scen, mode, glim), g in df.groupby(['scenario', 'mode', 'glim_pct']):
        g = g.sort_values('bound_scale')
        b1 = g[g['bound_scale'] == 1.0]
        if not len(b1):
            continue
        base_ok = bool(b1.iloc[0]['has_solution'])
        for _, r in g[g['bound_scale'] > 1.0].iterrows():
            if not base_ok and bool(r['has_solution']):
                flips.append((scen, mode, glim, r['bound_scale']))
            elif base_ok and bool(r['has_solution']):
                b, v = float(b1.iloc[0]['di_year1']), float(r['di_year1'])
                if b and (v - b) / b > 0.01:
                    quality.append((scen, mode, glim, r['bound_scale'],
                                    100.0 * (v - b) / b))
    if flips:
        print('SPURIOUS INFEASIBILITY -- the bounds, not the plan, are the cause:')
        for s, m, gl, bs in flips:
            print(f'  {s} mode={m} glim={gl}: infeasible at 1x, solvable at {bs:g}x')
    else:
        print('No infeasible -> feasible flips. The bounds are not causing '
              'spurious infeasibility on this corpus.')
    if quality:
        print('SILENT QUALITY LOSS -- the bounds were clipping the optimum:')
        for s, m, gl, bs, d in quality:
            print(f'  {s} mode={m} glim={gl}: DI +{d:.2f}% at {bs:g}x')
    else:
        print('No silent quality loss: loosening the bounds did not improve any optimum.')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--params-dir', action='append', default=None,
                    help='directory of scenario CSVs; repeatable. Default: params/')
    ap.add_argument('--out', default=None, help='output CSV path')
    ap.add_argument('--quick', action='store_true', help='mode 0 only')
    ap.add_argument('--bounds', action='store_true',
                    help='sweep bounds_scale 1/2/4 instead of the gap grid')
    ap.add_argument('--tout', type=float, default=TOUT)
    ap.add_argument('--tol', type=float, default=0.5,
                    help='objective %% you consider inside forecast noise (default 0.5)')
    ap.add_argument('--summary', default=None,
                    help='re-print the summary for an existing CSV and exit')
    ap.add_argument('--verbose', action='store_true', help='let SCIP log to stdout')
    args = ap.parse_args()

    if args.summary:
        df = pd.read_csv(args.summary)
        summarize(df, args.tol)
        if df['bound_scale'].nunique() > 1:
            report_bounds(df)
        return

    dirs = args.params_dir or ['params']
    paths = []
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, '*.csv'))):
            if not is_modern(path):
                print(f'SKIP {path}: legacy format (no fage1, or rors < 1)')
                continue
            paths.append(path)
    # Same scenario present in two clones: keep the first, note the duplicate.
    seen, uniq = {}, []
    for path in paths:
        key = os.path.basename(path)
        if key in seen:
            print(f'SKIP {path}: same filename as {seen[key]}')
            continue
        seen[key] = path
        uniq.append(path)
    paths = uniq
    if not paths:
        print('No modern-format scenarios found.')
        return

    modes = [0] if args.quick else MODES
    if args.bounds:
        glims, scales = [0.25], BOUND_SCALES
    else:
        glims, scales = GLIMS, [1.0]

    out = args.out or os.path.join(
        'data', '_bench_%s.csv' % _dt.datetime.now().strftime('%Y%m%d_%H%M%S'))
    n = len(paths) * len(modes) * len(glims) * len(scales)
    print(f'{len(paths)} scenarios x {len(modes)} modes x {len(glims)} gap limits '
          f'x {len(scales)} bound scales = {n} runs, tout={args.tout:g}s')
    print(f'Worst case {n * args.tout / 60:.0f} min if every run hits the timeout; '
          f'typically far less.\n')

    df = collect(paths, modes, glims, args.tout, scales, out, quiet=not args.verbose)
    if args.bounds:
        report_bounds(df)
    else:
        summarize(df, args.tol)


if __name__ == '__main__':
    main()
