# backend.py — PyWebView Api and worker thread (R3 plan)
# Copyright (c) 2020-5 Doug Currie

import os
import threading
import queue
import sys
import json
from io import StringIO

import pandas as pd
import webview

from planner import make_planning_datadict, PARAM_DEFAULTS, min_hd_year, max_hd_year

# Resolve relative save/load paths against app directory (so params/_2025_2.csv works from any CWD)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
from solver import oorp, three_peat, walk
from renderer import render_dd, render_three_peat

_INT_PARAMS = {
    'byear', 'aage1', 'aage2', 'fage1', 'fage2', 'refa1', 'refa2',
    'reta1', 'reta2', 'page1', 'page2',
    'yr01', 'yr02', 'yr03', 'yr04', 'yr05', 'yr06', 'yr07', 'yr08',
    'fstat', 'glide', 'spndm', 'ssabr',
    'pr01', 'pr02', 'pr03', 'pr04', 'pr05', 'pr06', 'pr07', 'pr08',
    'popt1', 'popt2',
}
_STR_PARAMS = {
    'tx01', 'tx02', 'tx03', 'tx04', 'tx05', 'tx06', 'tx07', 'tx08',
    'rothl', 'hist',
}


class _QueueWriter:
    """Redirects sys.stdout writes to a queue for JS polling."""
    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s.strip():
            self.q.put(s)

    def flush(self):
        pass


class Api:
    def __init__(self):
        self.params = dict(PARAM_DEFAULTS)
        self._log_queue = queue.Queue()
        self._running = False
        self.window = None  # set by main.py after create_window

    def _coerce_one(self, key, val):
        if key in _INT_PARAMS:
            return int(float(val))
        if key in _STR_PARAMS:
            return str(val)
        return float(val)

    def _coerce_types(self, d):
        return {k: self._coerce_one(k, v) for k, v in d.items()}

    def ping(self):
        """Return a string so the frontend can verify the bridge round-trip (e.g. on Cocoa)."""
        return 'pong'

    def get_params(self):
        return self.params

    def set_params(self, params_dict):
        """Called by JS before run_projection to sync form state."""
        self.params.update(self._coerce_types(params_dict))
        return {'ok': True}

    def _resolve_path(self, filepath):
        """Resolve relative paths against app directory so Load/Save work regardless of CWD."""
        if not filepath or not str(filepath).strip():
            return None
        p = str(filepath).strip()
        if not os.path.isabs(p):
            p = os.path.join(_APP_DIR, p)
        return p

    def save_params(self, filepath):
        path = self._resolve_path(filepath)
        if not path:
            return {'ok': False, 'error': 'No file path given'}
        ps = pd.Series(self.params)
        ps.to_csv(path)
        return {'ok': True}

    def load_params(self, filepath):
        path = self._resolve_path(filepath)
        if not path:
            return self.params
        if not os.path.isfile(path):
            raise FileNotFoundError(f'Params file not found: {path}')
        ps = pd.read_csv(path, index_col=0, keep_default_na=False)
        col = ps.columns[0]
        for key in PARAM_DEFAULTS:
            if key in ps.index:
                self.params[key] = self._coerce_one(key, ps.loc[key, col])
        return self.params

    def get_params_csv(self):
        """Return params as CSV string for clipboard copy."""
        return pd.Series(self.params).to_csv(None)

    def load_params_from_csv(self, csv_string):
        """Load params from CSV text (clipboard paste). Returns updated params."""
        ps = pd.read_csv(StringIO(csv_string), index_col=0, keep_default_na=False)
        col = ps.columns[0]
        for key in PARAM_DEFAULTS:
            if key in ps.index:
                self.params[key] = self._coerce_one(key, ps.loc[key, col])
        return self.params

    def get_hist_options(self):
        return {'min': int(min_hd_year), 'max': int(max_hd_year)}

    def run_projection(self, mode, testmode, tout, glim, efname, run_iis=False):
        """Called from JS Run button. Returns immediately; work runs in thread.

        run_iis: when True, if the solve is infeasible, run IIS (generateIIS); expensive.
        """
        if self._running:
            return {'error': 'already running'}
        self._running = True
        t = threading.Thread(
            target=self._run_worker,
            args=(int(mode), int(testmode), float(tout), float(glim), str(efname), bool(run_iis)),
            daemon=True,
        )
        t.start()
        return {'ok': True}

    def _run_worker(self, mode, testmode, tout, glim, efname, run_iis=False):
        def warn_cb(msg):
            self.window.evaluate_js(f'appendWarning({json.dumps(msg)})')

        def iis_prepare_cb(seconds):
            """Before IIS: drop queued SCIP text, clear warning + log panes, show status."""
            try:
                while True:
                    self._log_queue.get_nowait()
            except queue.Empty:
                pass
            msg = (
                f'Computing IIS (irreducible infeasible subsystem); '
                f'time limit {seconds:g} s (same as solve limit).'
            )
            print(msg, flush=True)
            msg_json = json.dumps(msg)
            # One round-trip: set pause flag so JS stops calling poll_log during IIS (avoids
            # main thread blocking on GIL while worker runs generateIIS).
            self.window.evaluate_js(
                '(function(){'
                'window.__eorpPauseLogPoll=true;'
                'clearWarningsAndScipLogForIIS();'
                f'appendWarning({msg_json});'
                'void document.documentElement.offsetHeight;'
                '})();'
            )

        old_stdout = sys.stdout
        sys.stdout = _QueueWriter(self._log_queue)
        try:
            if testmode == 4:
                result = walk(self.params, mode, tout, glim, efname, warn_cb=warn_cb)
                (worst_dd, worst_year, worst_di, fname) = result
                items = render_dd(worst_dd, fname)
            elif testmode == 3:
                result = three_peat(self.params, mode, tout, glim, efname, warn_cb=warn_cb)
                (rf, sm, fname) = result
                items = render_three_peat(rf, sm)
            else:
                objt = 'net_pretax' if testmode == 2 else 0
                test = 'test_losses' if testmode == 1 else ''
                result = oorp(
                    self.params,
                    mode,
                    objt,
                    test,
                    tout,
                    glim,
                    fname=efname,
                    warn_cb=warn_cb,
                    iis_prepare_cb=iis_prepare_cb if run_iis else None,
                    run_iis=run_iis,
                )
                (dd, status, net_pretax, di, stage, gap, stime, iis_names) = result
                items = render_dd(dd, efname, iis_names=iis_names)

            self.window.evaluate_js(f'renderResults({json.dumps(items)})')
        except Exception:
            import traceback
            self.window.evaluate_js(f'appendWarning({json.dumps(traceback.format_exc())})')
        finally:
            sys.stdout = old_stdout
            self._running = False
            self.window.evaluate_js('runFinished()')

    def poll_log(self):
        """JS polls this ~200ms to drain SCIP progress text."""
        lines = []
        try:
            while True:
                lines.append(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        return '\n'.join(lines)
