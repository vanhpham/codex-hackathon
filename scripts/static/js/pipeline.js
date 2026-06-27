/* ===== Pipeline Visualization Module ===== */
window.Pipeline = (function () {
  'use strict';

  var STAGES = [
    { id: 'prompt',     icon: '📝', label: 'Engineer\nPrompt',      pane: 'stagePrompt' },
    { id: 'openai',     icon: '🤖', label: 'OpenAI\nRaw Plan',      pane: 'stageRaw' },
    { id: 'gate',       icon: '🛡️', label: 'Schema +\nPolicy Gate',  pane: 'stageGate' },
    { id: 'simulator',  icon: '🧪', label: 'Local\nSimulator',      pane: 'stageSim' },
    { id: 'verify',     icon: '🔬', label: 'Verification\nMatrix',   pane: 'stageVerify' },
    { id: 'invariants', icon: '🔒', label: 'Invariant\nChecks',      pane: 'stageInvariants' },
    { id: 'risk',       icon: '📊', label: 'Risk\nReport',           pane: 'stageRisk' },
    { id: 'canary',     icon: '📦', label: 'Canary\nPayload',        pane: 'stageCanary' },
    { id: 'runtime',    icon: '🖧', label: 'Edge\nRuntime',          pane: 'stageRuntime' },
  ];

  var stageStatus = {};
  var activeStage = 'prompt';

  function init() {
    STAGES.forEach(function (s) { stageStatus[s.id] = 'idle'; });
    render();
    selectStage('prompt');
    _bindTabs();
  }

  function render() {
    var container = document.getElementById('pipelineFlow');
    if (!container) return;
    var html = '';
    STAGES.forEach(function (stage, i) {
      var status = stageStatus[stage.id] || 'idle';
      var isActive = stage.id === activeStage;
      html += '<div class="pipeline-node ' + status + (isActive ? ' active' : '') + '" data-stage="' + stage.id + '" onclick="Pipeline.selectStage(\'' + stage.id + '\')">';
      html += '  <div class="node-icon">' + stage.icon + '</div>';
      html += '  <div class="node-label">' + stage.label.replace('\n', '<br>') + '</div>';
      html += '  <div class="node-status">' + _statusLabel(status) + '</div>';
      html += '</div>';
      if (i < STAGES.length - 1) {
        var connStatus = _connectorStatus(i);
        html += '<div class="pipeline-connector ' + connStatus + '"></div>';
      }
    });
    container.innerHTML = html;
  }

  function _statusLabel(status) {
    var map = { idle: '—', running: 'running', passed: 'passed', failed: 'failed', skipped: 'skipped', done: 'done' };
    return map[status] || status;
  }

  function _connectorStatus(index) {
    var current = stageStatus[STAGES[index].id];
    var next = stageStatus[STAGES[index + 1].id];
    if (current === 'passed' && next !== 'idle') return 'passed';
    if (current === 'failed') return 'failed';
    if (current === 'running' || current === 'passed') return 'active';
    return '';
  }

  function selectStage(stageId) {
    activeStage = stageId;
    var stage = STAGES.find(function (s) { return s.id === stageId; });
    if (!stage) return;

    // Update header
    var idx = STAGES.indexOf(stage);
    var title = document.getElementById('detailTitle');
    if (title) title.textContent = stage.icon + ' ' + (idx + 1) + '. ' + stage.label.replace('\n', ' ');

    var badge = document.getElementById('detailBadge');
    if (badge) {
      var st = stageStatus[stageId] || 'idle';
      badge.className = 'badge ' + st;
      badge.textContent = st;
    }

    // Show only the matching pane
    STAGES.forEach(function (s) {
      var el = document.getElementById(s.pane);
      if (el) el.classList.toggle('hidden', s.id !== stageId);
    });

    render();
  }

  function setStatus(stageId, status) {
    stageStatus[stageId] = status;
    render();
    if (stageId === activeStage) {
      var badge = document.getElementById('detailBadge');
      if (badge) {
        badge.className = 'badge ' + status;
        badge.textContent = status;
      }
    }
  }

  function setAllIdle() {
    STAGES.forEach(function (s) { stageStatus[s.id] = 'idle'; });
    render();
  }

  function setRunning(stageId) {
    STAGES.forEach(function (s) {
      var idx = STAGES.indexOf(s);
      var targetIdx = STAGES.findIndex(function (t) { return t.id === stageId; });
      if (idx < targetIdx && stageStatus[s.id] === 'running') stageStatus[s.id] = 'passed';
    });
    stageStatus[stageId] = 'running';
    render();
  }

  function getStages() { return STAGES; }
  function getActiveStage() { return activeStage; }

  function _bindTabs() {
    // Debug tabs
    var tabs = document.querySelectorAll('.debug-tab');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.remove('active'); });
        tab.classList.add('active');
        var panes = document.querySelectorAll('.debug-pane');
        panes.forEach(function (p) { p.classList.remove('active'); });
        var target = document.getElementById(tab.getAttribute('data-tab'));
        if (target) target.classList.add('active');
      });
    });
  }

  return {
    init: init,
    render: render,
    selectStage: selectStage,
    setStatus: setStatus,
    setAllIdle: setAllIdle,
    setRunning: setRunning,
    getStages: getStages,
    getActiveStage: getActiveStage,
    STAGES: STAGES,
  };
})();
