/* ===== SwarmForge App Controller ===== */
window.App = (function () {
  'use strict';

  var latestResult = null;
  var latestReadyPayload = null;

  /* --- Init --- */
  function init() {
    Pipeline.init();
    refreshState();
    Debug.loadTraces();
    setInterval(refreshState, 2000);
    setInterval(function () { Debug.loadTraces(); }, 5000);
  }

  /* --- API --- */
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

  /* --- State Refresh --- */
  function refreshState() {
    Promise.all([
      _fetch('/api/state'),
      _fetch('/api/events')
    ]).then(function (results) {
      var state = results[0];
      var events = results[1];
      renderSummary(state);
      renderFleet(state);
      renderCanaryDecision(state);
      Debug.renderTelemetryTimeline(events);
      _updateHeaderBadges(state);
    }).catch(function () {});
  }

  function _updateHeaderBadges(state) {
    _el('brokerPill').textContent = 'broker: ' + (state.broker_mode || '—');
    _el('fleetPill').textContent = 'fleet: ' + (state.nodes_with_config || 0) + '/' + (state.node_count || 0);
    var d = state.last_dispatch;
    _el('dispatchPill').textContent = 'dispatch: ' + (d && d.run_id ? d.run_id : '—');
  }

  /* --- Summary Cards --- */
  function renderSummary(state) {
    _el('sumNodes').textContent = state.node_count || 0;
    _el('sumNodesDetail').textContent = 'configured: ' + (state.nodes_with_config || 0);
    _el('sumBroker').textContent = state.broker_mode || '—';
    _el('sumBrokerDetail').textContent = 'prefix: ' + (state.node_prefix || '—');

    var vm = state.verification_metrics || {};
    var eval_ = state.last_evaluation || {};
    var decision = vm.decision || eval_.decision || '—';
    var dc = decision === 'ready_for_canary' || decision === 'promote' ? 'good'
           : decision === 'blocked' || decision === 'rollback' ? 'bad' : '';
    _el('sumDecision').textContent = decision;
    _el('sumDecision').className = 'value ' + dc;
    var pr = vm.pass_rate != null ? Math.round(vm.pass_rate * 100) + '%' : '—';
    var rs = vm.risk_score != null ? vm.risk_score.toFixed(3) : '—';
    _el('sumDecisionDetail').textContent = 'pass rate: ' + pr + ' · risk: ' + rs;

    var d = state.last_dispatch;
    _el('sumRunId').textContent = eval_.run_id || (d && d.run_id) || '—';
    _el('sumRunDetail').textContent = 'targets: ' + (d && d.target_nodes ? d.target_nodes.join(', ') : '—');
  }

  /* --- Fleet Table --- */
  function renderFleet(state) {
    var tbody = _el('fleetTable');
    if (!tbody) return;
    var nodes = state.nodes || [];
    if (!nodes.length) { tbody.innerHTML = '<tr><td colspan="5" class="dim">No nodes</td></tr>'; return; }
    tbody.innerHTML = nodes.map(function (n) {
      var h = n.last_telemetry ? Number(n.last_telemetry.telemetry_health || 0).toFixed(3) : '—';
      var hClass = n.last_telemetry ? _healthClass(n.last_telemetry.telemetry_health) : 'dim';
      var hist = (n.telemetry_history || []).map(function (s) { return Number(s.telemetry_health || 0); });
      var spark = _buildSpark(hist.slice(-20));
      var cfg = n.current_config || {};
      var evt = n.last_event || {};
      return '<tr>'
        + '<td><strong>' + n.node_id + '</strong><div class="dim">samples: ' + n.telemetry_count + '</div></td>'
        + '<td class="' + hClass + '">' + h
          + (n.last_telemetry && n.last_telemetry.ts ? '<div class="dim">' + n.last_telemetry.ts + '</div>' : '') + '</td>'
        + '<td>' + spark + '</td>'
        + '<td><div>rate: ' + (cfg.sampling_rate_hz || '—') + '</div><div class="dim">deploy: ' + ((cfg.deployment || {}).percentage || '—') + '%</div></td>'
        + '<td><div>' + (evt.event || '—') + '</div><div class="dim">' + (evt.status || '') + (evt.reason ? ' · ' + evt.reason : '') + '</div></td>'
        + '</tr>';
    }).join('');
  }

  function _buildSpark(vals) {
    while (vals.length < 20) vals.unshift(0);
    return '<div class="spark">' + vals.map(function (v) {
      var h = Math.max(0, Math.min(1, v)) * 36;
      return '<span style="height:' + h + 'px" title="' + v.toFixed(3) + '"></span>';
    }).join('') + '</div>';
  }

  function _healthClass(v) { return v >= 0.95 ? 'good' : v >= 0.85 ? 'warn' : 'bad'; }

  function renderCanaryDecision(state) {
    var el = _el('canaryDecisionCard');
    var eval_ = state.last_evaluation || {};
    if (!eval_.decision) { el.innerHTML = '<div class="dim">No canary decision yet.</div>'; return; }
    var dc = eval_.decision === 'promote' ? 'good' : 'bad';
    el.innerHTML = '<div class="decision-banner ' + (eval_.decision === 'promote' ? 'ready' : 'blocked') + '">'
      + '<span class="icon">' + (eval_.decision === 'promote' ? '✅' : '⛔') + '</span>'
      + 'Decision: ' + eval_.decision
      + '</div>'
      + '<div class="dim">Samples: ' + (eval_.telemetry_samples_total || 0)
      + ' · All applied: ' + (eval_.all_nodes_applied || false)
      + ' · Health violation: ' + (eval_.telemetry_violation || false) + '</div>';
  }

  /* ===== MAIN PIPELINE RUN ===== */
  function runPipeline() {
    var prompt = _el('promptInput').value;
    var mode = _el('plannerMode').value;
    var scenarios = Number(_el('scenarioCount').value);
    var workers = Number(_el('workerCount').value);
    var adaptive = _el('adaptiveMode').value === 'true';

    // Reset UI
    Debug.clearPipelineLog();
    Pipeline.setAllIdle();
    _setGlobalBadge('running', 'Running');
    _el('btnGenerate').disabled = true;
    _el('btnDeploy').disabled = true;
    latestReadyPayload = null;

    // Stage 1: Prompt
    Pipeline.setStatus('prompt', 'passed');
    Debug.appendPipelineLog('✔ Prompt captured: ' + prompt.substring(0, 80) + '...');
    Debug.appendPipelineLog('  Mode=' + mode + ' scenarios=' + scenarios + ' workers=' + workers + ' adaptive=' + adaptive);

    // Stage 2-7: Running
    Pipeline.setRunning('openai');
    Debug.appendPipelineLog('⏳ Calling model client (' + mode + ')...');

    _fetch('/api/operator/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: prompt,
        planner_mode: mode,
        scenario_count: scenarios,
        workers: workers,
        adaptive: adaptive,
        suggest_settings: true,
        llm_suggestions: true,
      })
    }).then(function (result) {
      latestResult = result;
      _processResult(result);
    }).catch(function (err) {
      _handleError(err);
    }).finally(function () {
      _el('btnGenerate').disabled = false;
    });
  }

  function _processResult(r) {
    // Stage 2: OpenAI Raw
    _el('rawPlanLog').textContent = r.openai_raw_plan_json ? _json(r.openai_raw_plan_json) : 'No raw plan available.';
    Pipeline.setStatus('openai', r.openai_raw_plan_json ? 'passed' : 'failed');
    Debug.appendPipelineLog(r.openai_raw_plan_json ? '✔ Raw plan received from model' : '✘ No raw plan from model');

    // Stage 3: Schema Gate
    _el('gatePlanLog').textContent = r.parsed_plan ? _json(r.parsed_plan) : 'Parse failed or no plan.';
    var harness = r.harness || {};
    var gateOk = harness.plan_status === 'valid';
    Pipeline.setStatus('gate', gateOk ? 'passed' : 'failed');
    Debug.appendPipelineLog(gateOk ? '✔ Schema gate passed' : '✘ Schema gate failed: ' + (harness.validation_error || 'unknown'));

    if (harness.validation_error) {
      _el('gateInvariants').innerHTML = '<div class="invariant-item critical">'
        + '<span class="invariant-icon">🔴</span>'
        + '<div><div class="invariant-name">Validation Error</div>'
        + '<div class="invariant-reason">' + harness.validation_error + '</div></div></div>';
    } else {
      _el('gateInvariants').innerHTML = '<div class="invariant-item pass"><span class="invariant-icon">✅</span><div>Schema valid</div></div>';
    }

    // Stage 4: Simulator
    var sim = harness.simulation_result;
    if (sim) {
      _renderSimGauges(sim);
      _el('simLog').textContent = _json(sim);
      var simOk = harness.simulation_status === 'accepted';
      Pipeline.setStatus('simulator', simOk ? 'passed' : 'failed');
      Debug.appendPipelineLog(simOk ? '✔ Simulation accepted (score=' + (sim.score || 0).toFixed(3) + ')' : '✘ Simulation rejected: ' + (sim.reason || ''));
    } else {
      Pipeline.setStatus('simulator', harness.plan_status === 'valid' ? 'skipped' : 'skipped');
      _el('simLog').textContent = 'No simulation run (plan not valid).';
      _el('simGauges').innerHTML = '';
      Debug.appendPipelineLog('⊘ Simulation skipped');
    }

    // Stage 5: Verification
    var verif = r.verification;
    if (verif) {
      _renderVerifyGauges(verif);
      Pipeline.setStatus('verify', 'passed');
      Debug.appendPipelineLog('✔ Verification matrix completed: ' + verif.scenario_count + ' scenarios, pass_rate=' + (verif.pass_rate || 0).toFixed(3));

      // Scenario data for debug
      var trace = r.trace;
      if (trace && trace.run_id) {
        _fetch('/api/trace/' + encodeURIComponent(trace.run_id)).then(function (td) {
          if (td.scenario_records) Debug.setScenarioData(td.scenario_records);
          // Invariant data
          if (verif.case_results) Debug.renderInvariantList(verif.case_results);
        }).catch(function () {});
      }
    } else {
      Pipeline.setStatus('verify', 'skipped');
      _el('verifyGauges').innerHTML = '';
      _el('scenarioTable').innerHTML = '';
      Debug.appendPipelineLog('⊘ Verification skipped');
    }

    // Stage 6: Invariants (use verification results)
    if (verif && verif.case_results) {
      var hasCritical = verif.critical_failures && verif.critical_failures.length > 0;
      Pipeline.setStatus('invariants', hasCritical ? 'failed' : 'passed');
      Debug.renderInvariantList(verif.case_results);
      Debug.appendPipelineLog(hasCritical ? '✘ Critical invariant failures: ' + verif.critical_failures.join(', ') : '✔ All invariant checks OK');
    } else {
      Pipeline.setStatus('invariants', 'skipped');
    }

    // Stage 7: Risk Report
    if (verif) {
      var decision = verif.decision || (r.ready_payload ? 'ready_for_canary' : 'blocked');
      Pipeline.setStatus('risk', decision === 'ready_for_canary' ? 'passed' : 'failed');
      _renderRiskDetail(verif, decision, r.blocked_reason);
      Debug.appendPipelineLog('📊 Risk: score=' + (verif.risk_score || 0).toFixed(3) + ' decision=' + decision);
    } else {
      var bDecision = r.ready_payload ? 'ready_for_canary' : 'blocked';
      Pipeline.setStatus('risk', bDecision === 'ready_for_canary' ? 'passed' : 'failed');
      _renderRiskDetail(null, bDecision, r.blocked_reason);
    }

    // Stage 8: Canary Payload
    latestReadyPayload = r.ready_payload || null;
    if (latestReadyPayload) {
      Pipeline.setStatus('canary', 'passed');
      _el('canaryPayloadLog').textContent = _json(latestReadyPayload);
      _el('canaryBadge').className = 'badge passed';
      _el('canaryBadge').textContent = 'ready';
      _el('btnDeploy').disabled = false;
      _el('dispatchRunId').value = latestReadyPayload.run_id || '';
      Debug.appendPipelineLog('✔ Canary payload built: run_id=' + latestReadyPayload.run_id);
    } else {
      Pipeline.setStatus('canary', 'failed');
      _el('canaryPayloadLog').textContent = 'No payload — plan blocked.';
      _el('canaryBadge').className = 'badge failed';
      _el('canaryBadge').textContent = 'blocked';
      _el('btnDeploy').disabled = true;
      Debug.appendPipelineLog('⛔ Canary payload NOT generated');
    }

    // Stage 9: Runtime stays idle until deploy
    Pipeline.setStatus('runtime', 'idle');

    // Setting suggestions
    if (r.setting_suggestions) {
      Debug.renderSuggestions(r.setting_suggestions);
    }

    // Global badge
    var finalDecision = r.ready_payload ? 'ready_for_canary' : 'blocked';
    _setGlobalBadge(
      finalDecision === 'ready_for_canary' ? 'ready' : 'blocked',
      finalDecision === 'ready_for_canary' ? 'Ready for Canary' : 'Blocked'
    );
    Debug.appendPipelineLog('═══ Pipeline complete: ' + finalDecision + ' ═══');

    refreshState();
    Debug.loadTraces();
  }

  function _handleError(err) {
    _setGlobalBadge('failed', 'Error');
    Pipeline.setStatus('openai', 'failed');
    Debug.appendPipelineLog('✘ PIPELINE ERROR: ' + err);
    _el('rawPlanLog').textContent = String(err);
  }

  /* --- Sim Gauges --- */
  function _renderSimGauges(sim) {
    var el = _el('simGauges');
    el.innerHTML = _gauge('Noise Before', sim.noise_score_before, 1, '')
      + _gauge('Noise After', sim.noise_score_after, 1, sim.noise_score_after < sim.noise_score_before ? 'good' : 'bad')
      + _gauge('Noise Reduction', sim.noise_reduction_ratio, 1, 'good')
      + _gauge('BW Before', sim.bandwidth_before_kbps, 50, '', 'kbps')
      + _gauge('BW After', sim.bandwidth_after_kbps, 50, sim.bandwidth_after_kbps < sim.bandwidth_before_kbps ? 'good' : 'bad', 'kbps')
      + _gauge('Latency', sim.latency_penalty_ms, 250, sim.latency_penalty_ms < 200 ? 'good' : 'warn', 'ms')
      + _gauge('Score', sim.score, 1, sim.score >= 0.6 ? 'good' : 'bad');
  }

  function _renderVerifyGauges(v) {
    var el = _el('verifyGauges');
    el.innerHTML = _gauge('Pass Rate', v.pass_rate, 1, v.pass_rate >= 0.85 ? 'good' : 'bad', '', true)
      + _gauge('Risk Score', v.risk_score, 1, v.risk_score <= 0.25 ? 'good' : 'bad')
      + _gauge('Scenarios', v.scenario_count, v.scenario_count, '', '')
      + _gauge('Passed', v.passed_count, v.scenario_count, 'good')
      + _gauge('Failed', v.failed_count, v.scenario_count, v.failed_count > 0 ? 'bad' : 'good');

    // Scenario table
    var table = _el('scenarioTable');
    if (v.failed_scenarios && v.failed_scenarios.length) {
      table.innerHTML = '<table class="data-table"><thead><tr><th>Failed Scenario ID</th></tr></thead><tbody>'
        + v.failed_scenarios.slice(0, 20).map(function (s) { return '<tr><td class="bad">' + s + '</td></tr>'; }).join('')
        + '</tbody></table>';
    } else {
      table.innerHTML = '<div class="dim mt-8">All scenarios passed ✅</div>';
    }
  }

  function _renderRiskDetail(verif, decision, blockedReason) {
    var banner = _el('decisionBanner');
    var isReady = decision === 'ready_for_canary';
    banner.innerHTML = '<div class="decision-banner ' + (isReady ? 'ready' : 'blocked') + '">'
      + '<span class="icon">' + (isReady ? '✅' : '⛔') + '</span>'
      + (isReady ? 'READY FOR CANARY' : 'BLOCKED') + '</div>';

    var detail = _el('riskDetail');
    var html = '';
    if (verif) {
      html += '<div><h4>Metrics</h4>'
        + '<div class="dim mt-8">Pass rate: <strong class="' + (verif.pass_rate >= 0.85 ? 'good' : 'bad') + '">' + (verif.pass_rate * 100).toFixed(1) + '%</strong></div>'
        + '<div class="dim">Risk score: <strong class="' + (verif.risk_score <= 0.25 ? 'good' : 'bad') + '">' + verif.risk_score.toFixed(4) + '</strong></div>'
        + '<div class="dim">Scenarios: ' + verif.scenario_count + ' (passed: ' + verif.passed_count + ', failed: ' + verif.failed_count + ')</div>';
      if (verif.worst_case) {
        html += '<div class="dim mt-8">Worst case: ' + verif.worst_case.scenario_id + ' (health=' + (verif.worst_case.telemetry_health || 0).toFixed(3) + ')</div>';
      }
      if (verif.critical_failures && verif.critical_failures.length) {
        html += '<div class="bad mt-8">Critical: ' + verif.critical_failures.join(', ') + '</div>';
      }
      html += '</div>';
    }
    if (blockedReason) {
      html += '<div><h4>Block Reason</h4><pre class="log-block compact mt-8">' + _json(blockedReason) + '</pre></div>';
    }
    detail.innerHTML = html;
  }

  function _gauge(label, value, max, colorClass, unit, isPercent) {
    var display = value != null ? (isPercent ? (value * 100).toFixed(1) + '%' : (typeof value === 'number' ? value.toFixed(3) : value)) : '—';
    if (unit) display += ' ' + unit;
    var pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
    var fillClass = colorClass || (pct > 70 ? 'good' : pct > 40 ? 'warn' : 'bad');
    return '<div class="gauge">'
      + '<div class="gauge-value ' + colorClass + '">' + display + '</div>'
      + '<div class="gauge-label">' + label + '</div>'
      + '<div class="gauge-bar"><div class="gauge-fill ' + fillClass + '" style="width:' + pct + '%"></div></div>'
      + '</div>';
  }

  /* --- Deploy --- */
  function deployCanary() {
    if (!latestReadyPayload) {
      _setGlobalBadge('failed', 'No Payload');
      return;
    }
    Pipeline.setRunning('runtime');
    Debug.appendPipelineLog('🚀 Deploying canary: run_id=' + latestReadyPayload.run_id);

    var pct = Number(_el('dispatchPct').value) || 5;
    var samples = Number(_el('dispatchSamples').value) || 1;

    _fetch('/api/dispatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ready_payload: latestReadyPayload,
        percentage: pct,
        telemetry_samples_per_node: samples,
      })
    }).then(function (result) {
      Pipeline.setStatus('runtime', 'passed');
      _el('dispatchLog').textContent = _json(result);
      Debug.appendPipelineLog('✔ Dispatch complete');
      refreshState();
    }).catch(function (err) {
      Pipeline.setStatus('runtime', 'failed');
      _el('dispatchLog').textContent = String(err);
      Debug.appendPipelineLog('✘ Dispatch failed: ' + err);
    });
  }

  function manualDispatch() {
    var payload;
    try {
      payload = latestReadyPayload || JSON.parse(_el('canaryPayloadLog').textContent);
    } catch (e) {
      _el('dispatchLog').textContent = 'Invalid payload JSON';
      return;
    }
    latestReadyPayload = payload;
    deployCanary();
  }

  /* --- Utility --- */
  function copyText(id) {
    var el = _el(id);
    if (el && navigator.clipboard) navigator.clipboard.writeText(el.textContent).catch(function () {});
  }

  function _setGlobalBadge(cls, text) {
    var el = _el('globalState');
    el.className = 'badge ' + cls;
    el.textContent = text;
  }

  function _el(id) { return document.getElementById(id); }

  /* --- Boot --- */
  document.addEventListener('DOMContentLoaded', init);

  return {
    runPipeline: runPipeline,
    deployCanary: deployCanary,
    manualDispatch: manualDispatch,
    copyText: copyText,
    refreshState: refreshState,
  };
})();
