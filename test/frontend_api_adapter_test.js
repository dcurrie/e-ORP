#!/usr/bin/env node
/**
 * Test the cross-platform API adapter logic.
 * The frontend uses snake_case; Cocoa may expose snake_case, other backends use camelCase.
 * normalizeApi(raw) must return an object that supports snake_case calls whether raw uses
 * snake_case or camelCase.
 *
 * Run: node test/frontend_api_adapter_test.js
 */

function normalizeApi(raw) {
  if (!raw) return null;
  return {
    ping: raw.ping,
    get_params: raw.get_params || raw.getParams,
    set_params: raw.set_params || raw.setParams,
    save_params: raw.save_params || raw.saveParams,
    load_params: raw.load_params || raw.loadParams,
    get_params_csv: raw.get_params_csv || raw.getParamsCsv,
    load_params_from_csv: raw.load_params_from_csv || raw.loadParamsFromCsv,
    get_hist_options: raw.get_hist_options || raw.getHistOptions,
    run_projection: raw.run_projection || raw.runProjection,
    poll_log: raw.poll_log || raw.pollLog
  };
}

// Mock raw API that only has camelCase (simulates Windows/Linux backend)
function mockCamelCaseApi() {
  const noop = () => Promise.resolve();
  return {
    getParams: noop,
    setParams: noop,
    saveParams: noop,
    loadParams: noop,
    getParamsCsv: noop,
    loadParamsFromCsv: noop,
    getHistOptions: () => Promise.resolve({ min: 1928, max: 2024 }),
    runProjection: noop,
    pollLog: () => Promise.resolve('')
  };
}

// Mock raw API that only has snake_case (simulates Cocoa backend)
function mockSnakeCaseApi() {
  const noop = () => Promise.resolve();
  return {
    get_params: noop,
    set_params: noop,
    save_params: noop,
    load_params: noop,
    get_params_csv: noop,
    load_params_from_csv: noop,
    get_hist_options: () => Promise.resolve({ min: 1928, max: 2024 }),
    run_projection: noop,
    poll_log: () => Promise.resolve('')
  };
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function testCamelCaseRaw() {
  const raw = mockCamelCaseApi();
  const api = normalizeApi(raw);
  assert(api, 'normalizeApi(camelCase raw) should return object');
  assert(typeof api.get_params === 'function', 'api.get_params should be function');
  assert(api.get_params === raw.getParams, 'api.get_params should be raw.getParams');
  assert(typeof api.set_params === 'function', 'api.set_params should be function');
  assert(api.set_params === raw.setParams, 'api.set_params should be raw.setParams');
  assert(api.get_hist_options === raw.getHistOptions, 'api.get_hist_options should be raw.getHistOptions');
  assert(api.run_projection === raw.runProjection, 'api.run_projection should be raw.runProjection');
  assert(api.poll_log === raw.pollLog, 'api.poll_log should be raw.pollLog');
  // Call one that returns a value
  return api.get_hist_options().then(opts => {
    assert(opts && opts.min === 1928 && opts.max === 2024, 'get_hist_options() should resolve with options');
  });
}

function testSnakeCaseRaw() {
  const raw = mockSnakeCaseApi();
  const api = normalizeApi(raw);
  assert(api, 'normalizeApi(snake_case raw) should return object');
  assert(api.get_params === raw.get_params, 'api.get_params should be raw.get_params');
  assert(api.set_params === raw.set_params, 'api.set_params should be raw.set_params');
  return api.get_hist_options().then(opts => {
    assert(opts && opts.min === 1928 && opts.max === 2024, 'get_hist_options() should resolve');
  });
}

function testNullRaw() {
  assert(normalizeApi(null) === null, 'normalizeApi(null) should return null');
  assert(normalizeApi(undefined) === null, 'normalizeApi(undefined) should return null');
}

async function run() {
  const tests = [
    ['null/undefined raw', () => testNullRaw()],
    ['camelCase raw', () => testCamelCaseRaw()],
    ['snake_case raw', () => testSnakeCaseRaw()]
  ];
  for (const [name, fn] of tests) {
    await fn();
    console.log('  ok:', name);
  }
  console.log('All frontend API adapter tests passed.');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
