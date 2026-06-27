/* ===== Debug Panel Module ===== */
window.Debug = (function () {
  'use strict';

  var traces = [];
  var selectedTraceId = '';
  var scenarioData = [];

  /* --- API helpers --- */
  function _fetch(url, opts) {
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (d) {
        if (!r.ok) throw new Error(d.error || 'Request failed ' + r.status);
        return d;
      });
    });
  }

  function _json(v) {
    if (typeof v === 'string') { try { return JSON.stringify(JSON.parse(v), null, 2); } catch (e) { return v; } }
    return v ? JSON.stringify(v, null, 2) : '';
  }

  /* --- Traces --- */
  function loadTraces() {
    return _fetch('/api/traces').then(function (data) {
      traces = data || [];
      renderTraceList();
      renderTraceSelect();
    }).catch(function (e) {
      _el('traceDetailLog').textContent = String(e);
    });
  }

  function renderTraceList() {
    var c = _el('traceListContainer');
    if (!traces.length) { c.innerHTML = '<div class="dim">No traces found.</div>'; return; }
    c.innerHTML = traces.map(function (t) {
      var cls = t.run_id === selectedTraceId ? 'trace-item selected' : 'trace-item';
      var dc = t.decision === 'ready_for_canary' ? 'good' : t.decision === 'blocked' ? 'bad' : 'dim';
      return '<div class="' + cls + '" onclick="Debug.pickTrace(\'' + t.run_id + '\')">'
        + '<div class="run-id">' + t.run_id + '</div>'
        + '<div class="meta"><span class="' + dc + '">' + (t.decision || '—') + '</span>'
        + ' · scenarios: ' + (t.scenario_count || 0)
        + ' · failed: ' + (t.failed_cases || 0)
        + ' · pass: ' + (t.pass_rate != null ? Math.round(t.pass_rate * 100) + '%' : '—')
        + ' · risk: ' + (t.risk_score != null ? t.risk_score.toFixed(3) : '—')
        + '</div><div class="meta">' + (t.created_at || '') + '</div></div>';
    }).join('');
  }

  function renderTraceSelect() {
    var s = _el('traceSelect');
    if (!s) return;
    s.innerHTML = traces.map(function (t) {
      return '<option value="' + t.run_id + '">' + t.run_id + ' | ' + (t.decision || '?') + '</option>';
    }).join('');
  }

  function pickTrace(runId) {
    selectedTraceId = runId;
    _el('replayRunId').value = runId;
    renderTraceList();
    loadTraceDetail(runId);
  }

  function loadTraceDetail(runId) {
    return _fetch('/api/trace/' + encodeURIComponent(runId)).then(function (data) {
      _el('traceDetailLog').textContent = _json(data);
    }).catch(function (e) {
      _el('traceDetailLog').textContent = String(e);
    });
  }

  function loadSelectedTrace() {
    var sel = _el('traceSelect');
    if (!sel || !sel.value) return;
    selectedTraceId = sel.value;
    loadTraceDetail(sel.value);
  }

  /* --- Replay --- */
  function replayScenario() {
    var runId = _el('replayRunId').value;
    var scenarioId = _el('replayScenarioId').value;
    if (!runId) { _el('replayOutput').textContent = 'run_id required'; return; }
    _fetch('/api/replay', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: runId, scenario_id: scenarioId || undefined })
    }).then(function (data) {
      _el('replayOutput').textContent = _json(data);
    }).catch(function (e) {
      _el('replayOutput').textContent = String(e);
    });
  }

  /* --- Scenario Inspector --- */
  function setScenarioData(data) {
    scenarioData = data || [];
    renderScenarios();
    _el('scenarioFilter').onchange = renderScenarios;
  }

  function renderScenarios() {
    var filter = _el('scenarioFilter').value;
    var filtered = scenarioData;
    if (filter === 'failed') filtered = scenarioData.filter(function (s) { return !s.result.accepted; });
    if (filter === 'passed') filtered = scenarioData.filter(function (s) { return s.result.accepted; });
    _el('scenarioFilterCount').textContent = filtered.length + ' / ' + scenarioData.length + ' scenarios';

    var container = _el('scenarioInspector');
    if (!filtered.length) { container.innerHTML = '<div class="dim">No matching scenarios.</div>'; return; }
    container.innerHTML = filtered.slice(0, 100).map(function (s) {
      var sc = s.scenario || {};
      var r = s.result || {};
      var cls = r.accepted ? 'scenario-card passed' : 'scenario-card failed';
      var failedInvs = (r.failed_invariants || []);
      var invText = failedInvs.length ? failedInvs.map(function (f) {
        return '<div class="invariant-item ' + (f.critical ? 'critical' : 'warning') + '">'
          + '<span class="invariant-icon">' + (f.critical ? '🔴' : '🟡') + '</span>'
          + '<div><div class="invariant-name">' + f.name + '</div>'
          + '<div class="invariant-reason">' + f.reason + '</div></div></div>';
      }).join('') : '';
      return '<div class="' + cls + '">'
        + '<div class="flex justify-between items-center">'
        + '<strong>' + (sc.scenario_id || '—') + '</strong>'
        + '<span class="badge ' + (r.accepted ? 'passed' : 'failed') + '">' + (r.accepted ? 'PASS' : 'FAIL') + '</span>'
        + '</div>'
        + '<div class="scenario-tags">'
        + _tag(sc.terrain) + _tag(sc.noise_level) + _tag(sc.network_profile)
        + _tag(sc.battery_state) + _tag(sc.sensor_fault) + _tag('fleet:' + sc.fleet_size)
        + _tag('seed:' + sc.seed)
        + '</div>'
        + (r.reason && !r.accepted ? '<div class="dim mt-8" style="font-size:.78rem">' + r.reason + '</div>' : '')
        + invText
        + '</div>';
    }).join('');
  }

  function _tag(val) {
    if (!val || val === 'none') return '';
    return '<span class="scenario-tag">' + val + '</span>';
  }

  /* --- Telemetry Timeline --- */
  function renderTelemetryTimeline(events) {
    var el = _el('telemetryTimeline');
    if (!events || !events.length) { el.innerHTML = 'No events yet.'; return; }
    var lines = events.slice().reverse().slice(0, 100).map(function (e) {
      var ts = e.ts ? new Date(e.ts * 1000).toLocaleTimeString() : '—';
      return '[' + ts + '] <strong>' + (e.type || '') + '</strong> · ' + (e.message || '');
    });
    el.innerHTML = lines.join('\n');
    _el('telemetryTimestamp').textContent = 'Updated: ' + new Date().toLocaleTimeString();
  }

  /* --- Setting Suggestions --- */
  function renderSuggestions(data) {
    var el = _el('suggestionsContainer');
    if (!data || !data.mutually_exclusive_options || !data.mutually_exclusive_options.length) {
      el.innerHTML = '<div class="dim">No suggestions available. Plan passed or not yet run.</div>';
      return;
    }
    var html = '<div class="dim mb-8">Reason: ' + (data.reason || '—') + '</div>'
      + '<div class="dim mb-12">Confidence: ' + (data.confidence != null ? (data.confidence * 100).toFixed(1) + '%' : '—') + '</div>';

    data.mutually_exclusive_options.forEach(function (opt, i) {
      html += '<div class="suggestion-card">';
      html += '<h4>Option ' + (i + 1) + ': ' + (opt.label || opt.description || 'Adjustment') + '</h4>';
      if (opt.changes) {
        Object.keys(opt.changes).forEach(function (key) {
          var c = opt.changes[key];
          html += '<div class="suggestion-field">'
            + '<span>' + key + '</span>'
            + '<span><span class="old">' + (c.from != null ? c.from : '—') + '</span>'
            + '<span class="arrow">→</span>'
            + '<span class="new">' + (c.to != null ? c.to : '—') + '</span></span></div>';
        });
      } else {
        html += '<pre class="log-block compact">' + JSON.stringify(opt, null, 2) + '</pre>';
      }
      html += '</div>';
    });

    if (data.risk_delta_preview) {
      html += '<div class="suggestion-card"><h4>Risk Delta Preview</h4>'
        + '<pre class="log-block compact">' + JSON.stringify(data.risk_delta_preview, null, 2) + '</pre></div>';
    }
    el.innerHTML = html;
  }

  /* --- Pipeline Log --- */
  function appendPipelineLog(msg) {
    var el = _el('pipelineLogOutput');
    var ts = new Date().toLocaleTimeString();
    var line = '[' + ts + '] ' + msg;
    if (el.textContent.indexOf('Pipeline idle') === 0) el.textContent = '';
    el.textContent += line + '\n';
    el.scrollTop = el.scrollHeight;
  }

  function clearPipelineLog() {
    _el('pipelineLogOutput').textContent = '';
  }

  /* --- Invariant rendering for stage --- */
  function renderInvariantList(caseResults) {
    var el = _el('invariantList');
    if (!caseResults || !caseResults.length) {
      el.innerHTML = '<div class="dim">No invariant data yet.</div>';
      return;
    }
    var allInvariants = {};
    caseResults.forEach(function (c) {
      (c.failed_invariants || []).forEach(function (f) {
        if (!allInvariants[f.name]) allInvariants[f.name] = { name: f.name, critical: f.critical, count: 0, reasons: [] };
        allInvariants[f.name].count++;
        if (allInvariants[f.name].reasons.length < 3) allInvariants[f.name].reasons.push(f.reason);
      });
    });

    // Also show passing invariants
    var checkedNames = ['rollback_enabled', 'canary_required', 'latency_within_budget', 'payload_within_cap', 'noise_not_worse', 'bandwidth_not_worse', 'telemetry_health_above_floor'];
    var html = '';
    checkedNames.forEach(function (name) {
      var inv = allInvariants[name];
      if (inv) {
        var cls = inv.critical ? 'critical' : 'warning';
        html += '<div class="invariant-item ' + cls + '">'
          + '<span class="invariant-icon">' + (inv.critical ? '🔴' : '🟡') + '</span>'
          + '<div><div class="invariant-name">' + inv.name + ' <span class="dim">(' + inv.count + ' failures)</span></div>'
          + '<div class="invariant-reason">' + inv.reasons.join('; ') + '</div></div></div>';
      } else {
        html += '<div class="invariant-item pass">'
          + '<span class="invariant-icon">✅</span>'
          + '<div><div class="invariant-name">' + name + '</div>'
          + '<div class="invariant-reason">All scenarios passed</div></div></div>';
      }
    });
    el.innerHTML = html;
  }

  function _el(id) { return document.getElementById(id); }

  return {
    loadTraces: loadTraces,
    loadSelectedTrace: loadSelectedTrace,
    pickTrace: pickTrace,
    replayScenario: replayScenario,
    setScenarioData: setScenarioData,
    renderScenarios: renderScenarios,
    renderTelemetryTimeline: renderTelemetryTimeline,
    renderSuggestions: renderSuggestions,
    appendPipelineLog: appendPipelineLog,
    clearPipelineLog: clearPipelineLog,
    renderInvariantList: renderInvariantList,
  };
})();
