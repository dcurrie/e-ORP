// e-ORP PyWebView frontend (Stage 4 — full form and results)
// Copyright (c) 2020-5 Doug Currie

let pywebview = null;
let logInterval = null;

// Parameter type map (mirrors backend _INT_PARAMS / _STR_PARAMS)
const INT_PARAMS = new Set([
  'byear', 'aage1', 'aage2', 'fage1', 'fage2', 'refa1', 'refa2', 'reta1', 'reta2',
  'page1', 'page2', 'yr01', 'yr02', 'yr03', 'yr04', 'yr05', 'yr06', 'yr07', 'yr08',
  'fstat', 'glide', 'spndm', 'ssabr',
  'pr01', 'pr02', 'pr03', 'pr04', 'pr05', 'pr06', 'pr07', 'pr08', 'popt1', 'popt2'
]);
const STR_PARAMS = new Set([
  'tx01', 'tx02', 'tx03', 'tx04', 'tx05', 'tx06', 'tx07', 'tx08', 'rothl', 'hist'
]);

function coerceParam(key, val) {
  const v = String(val).trim();
  if (INT_PARAMS.has(key)) return v === '' ? 0 : parseInt(v, 10);
  if (STR_PARAMS.has(key)) return v;
  return v === '' ? 0 : parseFloat(v);
}

function collectParams() {
  const params = {};
  document.querySelectorAll('[data-param]').forEach(el => {
    const key = el.getAttribute('data-param');
    params[key] = coerceParam(key, el.value);
  });
  return params;
}

function populateForm(params) {
  if (!params) return;
  document.querySelectorAll('[data-param]').forEach(el => {
    const key = el.getAttribute('data-param');
    if (key in params) el.value = params[key];
  });
  updateGlidePath();
}

function updateGlidePath() {
  const enabled = parseInt(document.getElementById('glide').value, 10) !== 0;
  ['frhsd', 'frhsr', 'frhsa', 'frhbd', 'frhbr', 'frhba'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !enabled;
  });
}

function startLogPolling() {
  if (logInterval) clearInterval(logInterval);
  logInterval = setInterval(() => {
    if (!pywebview) return;
    pywebview.pollLog().then(text => {
      if (text) {
        const pre = document.getElementById('scip-log');
        pre.textContent += text;
        pre.scrollTop = pre.scrollHeight;
      }
    });
  }, 200);
}

function appendWarning(msg) {
  const div = document.getElementById('warnings');
  const p = document.createElement('p');
  p.className = 'warning';
  p.textContent = msg;
  div.appendChild(p);
}

function renderResults(items) {
  const panel = document.getElementById('results');
  panel.innerHTML = '';
  if (!items || !items.length) return;
  items.forEach((item, idx) => {
    if (item.type === 'plotly') {
      const div = document.createElement('div');
      div.id = 'chart-' + idx;
      div.className = 'chart';
      panel.appendChild(div);
      Plotly.newPlot(div.id, item.json.data, item.json.layout, { responsive: true });
    } else if (item.type === 'table') {
      const div = document.createElement('div');
      div.className = 'table-wrapper';
      div.innerHTML = item.html;
      panel.appendChild(div);
    } else if (item.type === 'heading') {
      const h3 = document.createElement('h3');
      h3.textContent = item.text;
      panel.appendChild(h3);
    }
  });
}

function runFinished() {
  const btn = document.getElementById('run-btn');
  if (btn) {
    btn.disabled = false;
    btn.textContent = 'Run Projection';
  }
}

function onRun() {
  const btn = document.getElementById('run-btn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Running...';
  }
  document.getElementById('warnings').innerHTML = '';
  document.getElementById('scip-log').textContent = '';
  document.getElementById('results').innerHTML = '';

  const mode = parseInt(document.getElementById('nlpomode').value, 10);
  const testmode = parseInt(document.getElementById('testmode').value, 10);
  const tout = parseFloat(document.getElementById('tout').value) || 60;
  const glim = parseFloat(document.getElementById('glim').value) || 0;
  const efname = (document.getElementById('efname') && document.getElementById('efname').value) || '';

  pywebview.setParams(collectParams());
  pywebview.runProjection(mode, testmode, tout, glim, efname);
}

// Attach Save/Load/Copy/Paste on DOM ready so they work even if pywebviewready fires late or fails
function onSaveClick() {
  if (!pywebview) { appendWarning('App not ready.'); return; }
  const pathEl = document.getElementById('pfname');
  const path = pathEl ? pathEl.value : '';
  pywebview.setParams(collectParams());
  pywebview.saveParams(path).then(result => {
    if (result && result.error) appendWarning('Save: ' + result.error);
  }).catch(e => appendWarning('Save failed: ' + (e.message || String(e))));
}

function onLoadClick() {
  if (!pywebview) { appendWarning('App not ready.'); return; }
  const pathEl = document.getElementById('pfname');
  const path = pathEl ? pathEl.value : '';
  pywebview.loadParams(path).then(params => {
    populateForm(params);
  }).catch(e => appendWarning('Load failed: ' + (e.message || String(e))));
}

function onCopyClick() {
  if (!pywebview) { appendWarning('App not ready.'); return; }
  pywebview.setParams(collectParams());
  pywebview.getParamsCsv().then(csv => {
    const el = document.getElementById('param-buf');
    if (el) el.value = csv;
  }).catch(e => appendWarning('Copy failed: ' + (e.message || String(e))));
}

function onPasteClick() {
  if (!pywebview) { appendWarning('App not ready.'); return; }
  const el = document.getElementById('param-buf');
  const text = el ? el.value : '';
  pywebview.loadParamsFromCsv(text).then(params => {
    populateForm(params);
  }).catch(e => appendWarning('Paste failed: ' + (e.message || String(e))));
}

function attachParamButtons() {
  const saveBtn = document.getElementById('save-btn');
  const loadBtn = document.getElementById('load-btn');
  const copyBtn = document.getElementById('copy-btn');
  const pasteBtn = document.getElementById('paste-btn');
  if (saveBtn) saveBtn.addEventListener('click', onSaveClick);
  if (loadBtn) loadBtn.addEventListener('click', onLoadClick);
  if (copyBtn) copyBtn.addEventListener('click', onCopyClick);
  if (pasteBtn) pasteBtn.addEventListener('click', onPasteClick);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', attachParamButtons);
} else {
  attachParamButtons();
}

function initBridge() {
  const api = (typeof pywebview !== 'undefined' && pywebview && pywebview.api)
    ? pywebview.api
    : (window.pywebview && window.pywebview.api);
  if (!api) return false;
  pywebview = api;

  api.getHistOptions().then(opts => {
    const sel = document.getElementById('hist');
    const first = sel.options[0];
    sel.innerHTML = '';
    sel.appendChild(first);
    for (let y = opts.min; y <= opts.max; y++) {
      const o = document.createElement('option');
      o.value = String(y);
      o.textContent = String(y);
      sel.appendChild(o);
    }
    return api.getParams();
  }).then(params => {
    populateForm(params);
  }).catch(e => {
    appendWarning('Startup: ' + (e.message || String(e)));
  });

  const glideEl = document.getElementById('glide');
  if (glideEl) glideEl.addEventListener('change', updateGlidePath);

  startLogPolling();

  const runBtn = document.getElementById('run-btn');
  if (runBtn) runBtn.addEventListener('click', onRun);
  return true;
}

window.addEventListener('pywebviewready', () => { initBridge(); });

// Fallback: if pywebviewready never fires (e.g. file:// or older build), poll for API
setTimeout(function poll() {
  if (pywebview) return;
  if (initBridge()) return;
  setTimeout(poll, 100);
}, 500);
