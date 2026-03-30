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
    // While IIS runs, Python holds the GIL for a long time; skip poll_log so the main
    // thread (Cocoa) can still paint the IIS warning instead of spinning.
    if (window.__eorpPauseLogPoll) return;
    const api = getApi();
    if (!api) return;
    api.poll_log().then(text => {
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

/** Called from Python when starting IIS after infeasible: clear warnings + SCIP log only. */
function clearWarningsAndScipLogForIIS() {
  const w = document.getElementById('warnings');
  const log = document.getElementById('scip-log');
  if (w) w.innerHTML = '';
  if (log) log.textContent = '';
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
      const titleEl = document.createElement('div');
      titleEl.className = 'result-section-title';
      titleEl.textContent = (item.text || '').replace(/^\s*###\s*/, '');
      panel.appendChild(titleEl);
    } else if (item.type === 'iis_report' && item.names && item.names.length) {
      const IIS_PREVIEW = 45;
      const names = item.names;
      const total = names.length;
      const wrap = document.createElement('div');
      wrap.className = 'iis-report';

      const intro = document.createElement('p');
      intro.className = 'iis-intro';
      intro.innerHTML =
        '<strong>' + total + ' constraints</strong> appear in SCIP’s irreducible infeasible subsystem (IIS) for this run. ' +
        'On a multi-year model, balances, RMDs, Roth limits, and tax brackets link across years, so the IIS is often ' +
        '<em>large</em> even though it is “irreducible” (dropping any one listed constraint would leave a feasible relaxation). ' +
        'Key constraints use readable names (e.g. <code>eorp_min_residual_final</code>, <code>eorp_disp_balance_y12</code>, <code>eorp_rothlim_y5</code>); the rest stay sequential <code>eorp_NNNNN</code>.';
      wrap.appendChild(intro);

      const hint = document.createElement('p');
      hint.className = 'iis-hint';
      hint.textContent =
        'Try adjusting the tightest inputs first (spending floor, minimum residual, Roth conversion caps, charity/QCD, ages). ' +
        'If the list is long, use Copy all names to search in solver source or an exported .lp file.';
      wrap.appendChild(hint);

      function appendNameLis(ul, arr) {
        arr.forEach(n => {
          const li = document.createElement('li');
          li.textContent = n;
          ul.appendChild(li);
        });
      }

      const ulTop = document.createElement('ul');
      ulTop.className = 'iis-list';
      const shown = total <= IIS_PREVIEW ? names : names.slice(0, IIS_PREVIEW);
      appendNameLis(ulTop, shown);
      wrap.appendChild(ulTop);

      if (total > IIS_PREVIEW) {
        const more = document.createElement('p');
        more.className = 'iis-more';
        more.textContent = 'Showing first ' + IIS_PREVIEW + ' of ' + total + '.';
        wrap.appendChild(more);
        const det = document.createElement('details');
        det.className = 'iis-details';
        const sum = document.createElement('summary');
        sum.textContent = 'Show remaining ' + (total - IIS_PREVIEW) + ' names';
        const ulRest = document.createElement('ul');
        ulRest.className = 'iis-list iis-list-rest';
        appendNameLis(ulRest, names.slice(IIS_PREVIEW));
        det.appendChild(sum);
        det.appendChild(ulRest);
        wrap.appendChild(det);
      }

      const copyRow = document.createElement('p');
      copyRow.className = 'iis-copy-row';
      const copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 'iis-copy-btn';
      copyBtn.textContent = 'Copy all names';
      copyBtn.addEventListener('click', () => {
        const text = names.join('\n');
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(() => {
            copyBtn.textContent = 'Copied';
            setTimeout(() => { copyBtn.textContent = 'Copy all names'; }, 2000);
          }).catch(() => {
            appendWarning('Could not copy to clipboard.');
          });
        } else {
          appendWarning('Clipboard API not available in this webview.');
        }
      });
      copyRow.appendChild(copyBtn);
      wrap.appendChild(copyRow);

      panel.appendChild(wrap);
    }
  });
}

function runFinished() {
  window.__eorpPauseLogPoll = false;
  const btn = document.getElementById('run-btn');
  if (btn) {
    btn.disabled = false;
    btn.textContent = 'Run Projection';
  }
}

// Bridge method names: Cocoa may expose snake_case; other backends (Windows/Linux) use camelCase.
// Normalize so app code can always use snake_case.
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

function getApi() {
  const raw = (window.pywebview && window.pywebview.api) || pywebview;
  return raw ? normalizeApi(raw) : null;
}

function onRun() {
  const api = getApi();
  if (!api) { appendWarning('Run: bridge not available'); return; }
  const btn = document.getElementById('run-btn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Running...';
  }
  document.getElementById('warnings').innerHTML = '';
  document.getElementById('scip-log').textContent = '';
  document.getElementById('results').innerHTML = '';
  window.__eorpPauseLogPoll = false;

  const mode = parseInt(document.getElementById('nlpomode').value, 10);
  const testmode = parseInt(document.getElementById('testmode').value, 10);
  const tout = parseFloat(document.getElementById('tout').value) || 60;
  const glim = parseFloat(document.getElementById('glim').value) || 0;
  const efname = (document.getElementById('efname') && document.getElementById('efname').value) || '';

  try {
    api.set_params(collectParams());
    var p = api.run_projection(mode, testmode, tout, glim, efname);
    if (p && typeof p.then === 'function') {
      p.catch(function (e) { appendWarning('Run failed: ' + (e && (e.message || e.toString()))); runFinished(); });
    }
  } catch (e) {
    appendWarning('Run error: ' + (e && (e.message || e.toString())));
    runFinished();
  }
}

// Attach Save/Load/Copy/Paste on DOM ready so they work even if pywebviewready fires late or fails
function onSaveClick() {
  const api = getApi();
  if (!api) { appendWarning('Save: App not ready.'); return; }
  const pathEl = document.getElementById('pfname');
  const path = pathEl ? pathEl.value : '';
  api.set_params(collectParams());
  api.save_params(path).then(result => {
    if (result && result.error) appendWarning('Save: ' + result.error);
  }).catch(e => appendWarning('Save failed: ' + (e.message || String(e))));
}

function onLoadClick() {
  const api = getApi();
  if (!api) { appendWarning('Load: App not ready.'); return; }
  const pathEl = document.getElementById('pfname');
  const path = pathEl ? pathEl.value : '';
  api.load_params(path).then(params => {
    populateForm(params);
  }).catch(e => appendWarning('Load failed: ' + (e.message || String(e))));
}

function onCopyClick() {
  const api = getApi();
  if (!api) { appendWarning('Copy: App not ready.'); return; }
  api.set_params(collectParams());
  api.get_params_csv().then(csv => {
    const el = document.getElementById('param-buf');
    if (el) el.value = csv;
  }).catch(e => appendWarning('Copy failed: ' + (e.message || String(e))));
}

function onPasteClick() {
  const api = getApi();
  if (!api) { appendWarning('Paste: App not ready.'); return; }
  const el = document.getElementById('param-buf');
  const text = el ? el.value : '';
  api.load_params_from_csv(text).then(params => {
    populateForm(params);
  }).catch(e => appendWarning('Paste failed: ' + (e.message || String(e))));
}

function attachParamButtons() {
  const saveBtn = document.getElementById('save-btn');
  const loadBtn = document.getElementById('load-btn');
  const copyBtn = document.getElementById('copy-btn');
  const pasteBtn = document.getElementById('paste-btn');
  const runBtn = document.getElementById('run-btn');
  if (saveBtn) saveBtn.addEventListener('click', onSaveClick);
  if (loadBtn) loadBtn.addEventListener('click', onLoadClick);
  if (copyBtn) copyBtn.addEventListener('click', onCopyClick);
  if (pasteBtn) pasteBtn.addEventListener('click', onPasteClick);
  if (runBtn) runBtn.addEventListener('click', onRun);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', attachParamButtons);
} else {
  attachParamButtons();
}

function setBridgeStatus(msg, className) {
  const el = document.getElementById('bridge-status');
  if (el) { el.textContent = msg; el.className = 'bridge-status ' + (className || ''); }
}

function initBridge() {
  /* Cocoa: ensure _jsApiCallback uses our stringify (see index.html head script). */
  if (window.pywebview && window.pywebview.platform === 'cocoa') {
    var stringify = (typeof window.pywebview.stringify === 'function')
      ? window.pywebview.stringify.bind(window.pywebview)
      : function(obj) { return JSON.stringify(obj); };
    var orig = window.pywebview._jsApiCallback;
    if (typeof orig === 'function') {
      window.pywebview._jsApiCallback = function(funcName, params, id) {
        var payload = stringify({ funcName: funcName, params: params, id: id });
        return window.webkit.messageHandlers.jsBridge.postMessage(payload);
      };
    }
  }
  const raw = (typeof pywebview !== 'undefined' && pywebview && pywebview.api)
    ? pywebview.api
    : (window.pywebview && window.pywebview.api);
  if (!raw) return false;
  pywebview = raw;
  setBridgeStatus('Ready', 'ready');

  const api = getApi();
  api.get_hist_options().then(opts => {
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
    return api.get_params();
  }).then(params => {
    populateForm(params);
  }).catch(e => {
    setBridgeStatus('Startup error — see Warnings', 'failed');
    appendWarning('Startup: ' + (e.message || String(e)));
  });

  const glideEl = document.getElementById('glide');
  if (glideEl) glideEl.addEventListener('change', updateGlidePath);

  startLogPolling();
  return true;
}

window.addEventListener('pywebviewready', () => { initBridge(); });

if (window.__eorpBridgeReadyFired) {
  initBridge();
}

// Fallback: if pywebviewready never fires, poll for API (e.g. late injection on Cocoa)
var pollCount = 0;
var pollMax = 150;
setTimeout(function poll() {
  if (pywebview) return;
  if (initBridge()) return;
  pollCount++;
  if (pollCount >= pollMax) {
    setBridgeStatus('Bridge not available — run from project dir: cd path/to/e-ORP && python main.py', 'failed');
    return;
  }
  setTimeout(poll, 80);
}, 100);
