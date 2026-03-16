#!/usr/bin/env python3
"""Tests for backend Api (params CSV round-trip). Run from repo root with venv."""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import Api
from planner import PARAM_DEFAULTS


def test_params_csv_roundtrip():
    api = Api()
    api.params['byear'] = 2030
    api.params['rorb'] = 2.5
    csv_string = api.get_params_csv()
    assert 'byear' in csv_string and '2030' in csv_string
    api2 = Api()
    api2.load_params_from_csv(csv_string)
    assert api2.params['byear'] == 2030
    assert api2.params['rorb'] == 2.5
    print("test_params_csv_roundtrip: OK")


def test_params_file_roundtrip():
    api = Api()
    api.params['aage1'] = 67
    api.params['hist'] = 'Use Values Below'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        path = f.name
    try:
        api.save_params(path)
        api2 = Api()
        api2.load_params(path)
        assert api2.params['aage1'] == 67
        assert api2.params['hist'] == 'Use Values Below'
        print("test_params_file_roundtrip: OK")
    finally:
        os.unlink(path)


def test_params_relative_path_load_save():
    """Load/save using relative path (e.g. params/file.csv) resolved against app dir."""
    api = Api()
    api.params['byear'] = 2028
    api.params['rorb'] = 2.0
    rel_path = os.path.join('params', 'test_desktop_save.csv')
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abs_path = os.path.join(app_dir, rel_path)
    try:
        api.save_params(rel_path)
        assert os.path.isfile(abs_path), abs_path
        api2 = Api()
        api2.load_params(rel_path)
        assert api2.params['byear'] == 2028
        assert api2.params['rorb'] == 2.0
        print("test_params_relative_path_load_save: OK")
    finally:
        if os.path.isfile(abs_path):
            os.unlink(abs_path)


if __name__ == '__main__':
    test_params_csv_roundtrip()
    test_params_file_roundtrip()
    test_params_relative_path_load_save()
    print("All backend tests passed.")
