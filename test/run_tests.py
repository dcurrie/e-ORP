#!/usr/bin/env python3
"""Run full desktop-app test suite (planner + backend). Run from repo root with venv."""
import subprocess
import sys
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(repo_root)
python = sys.executable

failed = []
for name in ('test_planner', 'test_backend', 'test_frontend_api_adapter'):
    path = os.path.join('test', name + '.py')
    r = subprocess.run([python, path], cwd=repo_root)
    if r.returncode != 0:
        failed.append(name)

if failed:
    print(f'\nFailed: {" ".join(failed)}', file=sys.stderr)
    sys.exit(1)
print('\nAll test modules passed.')
