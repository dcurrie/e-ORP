"""
Test the cross-platform API adapter logic (mirrors frontend app.js normalizeApi).

The frontend uses snake_case; Cocoa may expose snake_case, other backends use camelCase.
normalizeApi(raw) must return an object that supports snake_case keys whether raw uses
snake_case or camelCase. This module tests the same logic in Python so the test suite
does not require Node.
"""

import unittest


def normalize_api(raw):
    """Mirror of frontend normalizeApi: prefer snake_case, fall back to camelCase."""
    if raw is None:
        return None
    return {
        'ping': raw.get('ping'),
        'get_params': raw.get('get_params') or raw.get('getParams'),
        'set_params': raw.get('set_params') or raw.get('setParams'),
        'save_params': raw.get('save_params') or raw.get('saveParams'),
        'load_params': raw.get('load_params') or raw.get('loadParams'),
        'get_params_csv': raw.get('get_params_csv') or raw.get('getParamsCsv'),
        'load_params_from_csv': (
            raw.get('load_params_from_csv') or raw.get('loadParamsFromCsv')
        ),
        'get_hist_options': raw.get('get_hist_options') or raw.get('getHistOptions'),
        'run_projection': raw.get('run_projection') or raw.get('runProjection'),
        'poll_log': raw.get('poll_log') or raw.get('pollLog'),
    }


class TestFrontendApiAdapter(unittest.TestCase):
    def test_null_raw(self):
        self.assertIsNone(normalize_api(None))

    def test_camel_case_raw(self):
        """When backend exposes only camelCase (e.g. Windows/Linux), snake_case keys work."""
        get_params = object()
        set_params = object()
        raw = {
            'getParams': get_params,
            'setParams': set_params,
            'getHistOptions': lambda: {'min': 1928, 'max': 2024},
            'runProjection': object(),
            'pollLog': object(),
        }
        api = normalize_api(raw)
        self.assertIsNotNone(api)
        self.assertIs(api['get_params'], get_params)
        self.assertIs(api['set_params'], set_params)
        self.assertIs(api['get_hist_options'], raw['getHistOptions'])
        opts = api['get_hist_options']()
        self.assertEqual(opts['min'], 1928)
        self.assertEqual(opts['max'], 2024)

    def test_snake_case_raw(self):
        """When backend exposes snake_case (e.g. Cocoa), snake_case keys are used."""
        get_params = object()
        raw = {
            'get_params': get_params,
            'set_params': object(),
            'get_hist_options': lambda: {'min': 1928, 'max': 2024},
        }
        api = normalize_api(raw)
        self.assertIs(api['get_params'], get_params)
        self.assertIs(api['get_hist_options'], raw['get_hist_options'])


if __name__ == '__main__':
    unittest.main()
