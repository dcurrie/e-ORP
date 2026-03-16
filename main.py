# main.py — e-ORP PyWebView entry point (R3 plan)
# Copyright (c) 2020-5 Doug Currie
#
# Run from the project directory so the built-in server finds frontend/:
#   cd /path/to/e-ORP
#   python main.py
# Or with venv:  ./ORPy-venv/bin/python main.py
# For dev tools (to debug bridge):  python main.py --debug

import os
import sys
import webview
from backend import Api

if __name__ == '__main__':
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)

    api = Api()
    debug = '--debug' in sys.argv
    window = webview.create_window(
        'e-ORP — Optimal Retirement Planner',
        'frontend/index.html',
        js_api=api,
        width=1400,
        height=900,
        min_size=(900, 600),
    )
    api.window = window
    webview.start(debug=debug)
