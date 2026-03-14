# main.py — e-ORP PyWebView entry point (R3 plan)
# Copyright (c) 2020-5 Doug Currie

import os
import webview
from backend import Api

if __name__ == '__main__':
    # Use app directory as CWD so relative path is resolved and pywebview's
    # built-in HTTP server serves the page (required for js_api to inject).
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)

    api = Api()
    # Relative path so pywebview uses HTTP server, not file:// (file:// breaks js_api on some platforms)
    window = webview.create_window(
        'e-ORP — Optimal Retirement Planner',
        'frontend/index.html',
        js_api=api,
        width=1400,
        height=900,
        min_size=(900, 600),
    )
    api.window = window
    webview.start(debug=False)
