from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.edge_runtime import (
    EdgeNode,
    InMemoryBroker,
    dispatch_to_canary,
    evaluate_canary_dispatch,
)
from swarmforge.env import load_env_file
from swarmforge.harness import OpenAIResponsesPlanClient, PlanClient, run_harness
from swarmforge.mqtt_transport import PahoMqttTransport, RuntimeTransportUnavailable
from swarmforge.ota import build_ota_config
from swarmforge.scenarios import ScenarioSpec, generate_scenario_matrix
from swarmforge.schemas import OptimizationPlan
from swarmforge.setting_suggester import suggest_setting_adjustments
from swarmforge.traces import build_verification_trace, load_trace, make_run_id, replay_trace_case, save_trace
from swarmforge.verification import DEFAULT_ADAPTIVE_WORKERS, run_verification_matrix


DEFAULT_OPERATOR_PROMPT = (
    "Xe dang vao vung bun lay, rung lac manh. Hay giam sample rate xuong 2Hz, "
    "them median filter cho gia toc, va chuyen log level sang WARNING."
)

DEMO_PLAN = {
    "intent": "reduce_noise_and_bandwidth",
    "target_metric": "accelerometer",
    "sampling_rate_hz": 2,
    "log_level": "WARNING",
    "filter": {"type": "median", "window_size": 5},
    "telemetry_collection": {
        "metrics": ["accelerometer", "temperature", "battery"],
        "aggregation_window_seconds": 5,
        "publish_mode": "summary_and_anomalies",
        "max_payload_kbps": 8,
    },
    "deployment": {"strategy": "canary", "percentage": 5, "observation_window_seconds": 10},
    "rollback": {
        "enabled": True,
        "max_latency_ms": 250,
        "max_error_rate": 0.02,
        "min_telemetry_health": 0.95,
    },
}


class DemoPlanClient:
    def create_plan(self, prompt: str) -> dict[str, Any]:
        del prompt
        return dict(DEMO_PLAN)


INDEX_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>SwarmForge Sprint 7 - Visualization Lab</title>
  <style>
    :root {
      --bg: #f5f7fb;
      --card: #fff;
      --line: #d4d8de;
      --text: #1c2025;
      --muted: #666;
      --good: #0a7a37;
      --bad: #ab0c0c;
      --warn: #a36b00;
    }
    body {
      font-family: Inter, system-ui, sans-serif;
      margin: 16px;
      background: var(--bg);
      color: var(--text);
    }
    h1, h2, h3 {
      margin: 0 0 8px;
    }
    .page {
      max-width: 1500px;
      margin: 0 auto;
      display: grid;
      gap: 12px;
    }
    .row {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(12, 1fr);
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      overflow: hidden;
    }
    .col-12 { grid-column: span 12; }
    .col-8 { grid-column: span 8; }
    .col-4 { grid-column: span 4; }
    .col-6 { grid-column: span 6; }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 12px;
    }
    .summary-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fff;
    }
    .summary-card .label {
      font-size: 0.86rem;
      color: var(--muted);
    }
    .summary-card .value {
      font-size: 1.25rem;
      margin-top: 6px;
      font-weight: 600;
    }
    .muted { color: var(--muted); font-size: 0.9rem; }
    .good { color: var(--good); }
    .bad { color: var(--bad); }
    .warn { color: var(--warn); }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.93rem;
    }
    th, td {
      text-align: left;
      padding: 6px;
      border-bottom: 1px solid #eceef2;
      vertical-align: top;
    }
    th {
      background: #f8fafc;
      font-weight: 600;
      position: sticky;
      top: 0;
    }
    .toolbar {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 8px;
    }
    input, button, textarea, select {
      font: inherit;
    }
    button {
      padding: 6px 10px;
    }
    textarea {
      width: 100%;
      resize: vertical;
    }
    .log {
      max-height: 260px;
      overflow: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.82rem;
      background: #0b1220;
      color: #dce5f2;
      padding: 8px;
      border-radius: 6px;
    }
    .spark {
      display: grid;
      grid-template-columns: repeat(20, 1fr);
      gap: 2px;
      align-items: end;
      height: 60px;
    }
    .spark span {
      display: block;
      width: 100%;
      background: #d5e4ff;
      border-radius: 2px 2px 0 0;
      align-self: end;
      transition: height 0.15s;
    }
    .trace-list {
      max-height: 260px;
      overflow: auto;
    }
    .card-inline {
      display: grid;
      gap: 6px;
    }
    .decision {
      font-weight: 700;
      margin-bottom: 6px;
    }
    .pill {
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 0.8rem;
      border: 1px solid #cbd2db;
      background: #f7f9fc;
      margin-right: 6px;
    }
    .trace-item {
      padding: 6px;
      border: 1px solid var(--line);
      border-radius: 6px;
      margin-bottom: 6px;
      cursor: pointer;
      background: #fff;
    }
    .trace-item:hover {
      border-color: #7ca2ff;
    }
    .active { border-color: #2f62ff; box-shadow: 0 0 0 1px #2f62ff33; }
    .operator-grid {
      display: grid;
      grid-template-columns: minmax(320px, 1fr) minmax(320px, 1fr);
      gap: 12px;
    }
    .operator-controls {
      display: grid;
      gap: 8px;
    }
    .operator-controls textarea {
      min-height: 116px;
    }
    .mini-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(90px, 1fr));
      gap: 8px;
      align-items: end;
    }
    .mini-grid label {
      display: grid;
      gap: 4px;
      font-size: 0.86rem;
      color: var(--muted);
    }
    @media (max-width: 960px) {
      .operator-grid { grid-template-columns: 1fr; }
      .mini-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
    }
  </style>
</head>
<body>
  <div class="page">
    <h1>SwarmForge Sprint 7 - Runtime Visualization</h1>
    <p class="muted">Visualize verification-safe canary runtime, fleet telemetry, and trace evidence in one place.</p>

    <div class="summary" id="summaryCards"></div>

    <section class="panel col-12">
      <h3>Operator Console</h3>
      <div class="operator-grid">
        <div class="operator-controls">
          <textarea id="operatorPrompt">Xe dang vao vung bun lay, rung lac manh. Hay giam sample rate xuong 2Hz, them median filter cho gia toc, va chuyen log level sang WARNING.</textarea>
          <div class="mini-grid">
            <label>Planner
              <select id="plannerMode">
                <option value="openai" selected>OpenAI</option>
                <option value="demo">Demo</option>
              </select>
            </label>
            <label>Scenarios
              <input id="operatorScenarioCount" type="number" min="5" max="500" value="50" />
            </label>
            <label>Workers
              <input id="operatorWorkers" type="number" min="1" max="16" value="4" />
            </label>
            <label>Adaptive
              <select id="operatorAdaptive">
                <option value="true" selected>On</option>
                <option value="false">Off</option>
              </select>
            </label>
          </div>
          <div class="toolbar">
            <button onclick="runOperatorPlan()">Generate + Verify</button>
            <button onclick="deployVerifiedPlan()">Deploy Verified Canary</button>
            <span id="operatorState" class="muted">Idle</span>
          </div>
        </div>
        <pre class="log" id="operatorResult">No operator run yet.</pre>
      </div>
    </section>

    <div class="row">
      <section class="panel col-8">
        <h3>Fleet State</h3>
        <div class="toolbar">
          <button onclick="refreshAll()">Refresh</button>
          <span class="pill" id="brokerMode">broker: -</span>
          <span class="pill" id="fleetConfigured">configured: 0</span>
          <span class="pill" id="lastDispatch">last dispatch: -</span>
        </div>
        <div style="max-height: 340px; overflow: auto;">
          <table>
            <thead>
              <tr>
                <th>Node</th>
                <th>Telemetry</th>
                <th>Health History</th>
                <th>Config</th>
                <th>Last Event</th>
              </tr>
            </thead>
            <tbody id="fleetTable"></tbody>
          </table>
        </div>
      </section>
      <aside class="panel col-4">
        <h3>Canary Decision</h3>
        <div id="decisionCard" class="card-inline">
          <div class="muted">No decision yet.</div>
        </div>
        <div style="height: 12px;"></div>
        <h3>Dispatch Controls</h3>
        <div class="card-inline">
          <div><label>Run ID</label> <input id="run_id" value="run_manual_001" /></div>
          <div><label>Canary Percentage (%)</label> <input id="percentage" type="number" min="1" max="100" value="5" /></div>
          <div><label>Health Samples / Target Node</label> <input id="telemetrySamples" type="number" min="0" max="20" value="1" /></div>
          <div><label>Ready Payload JSON</label>
            <textarea id="payload" rows="13">{\"run_id\":\"run_manual_001\",\"plan\":{\"intent\":\"reduce_noise_and_bandwidth\",\"target_metric\":\"accelerometer\",\"sampling_rate_hz\":2,\"log_level\":\"WARNING\",\"filter\":{\"type\":\"median\",\"window_size\":5},\"telemetry_collection\":{\"metrics\":[\"accelerometer\",\"temperature\",\"battery\"],\"aggregation_window_seconds\":5,\"publish_mode\":\"summary_and_anomalies\",\"max_payload_kbps\":8},\"deployment\":{\"strategy\":\"canary\",\"percentage\":5,\"observation_window_seconds\":10},\"rollback\":{\"enabled\":true,\"max_latency_ms\":250,\"max_error_rate\":0.02,\"min_telemetry_health\":0.95}},\"verification\":{\"decision\":\"ready_for_canary\",\"risk_score\":0.1}}</textarea>
          </div>
          <div><button onclick="submitDispatch()">Dispatch Canary</button> <span id="dispatchState" class="muted"></span></div>
          <pre class="log" id="dispatchResult">No dispatch yet.</pre>
        </div>
      </aside>
    </div>

    <div class="row">
      <section class="panel col-6">
        <h3>Telemetry Event Timeline</h3>
        <div id="eventLog" class="log" style="max-height: 220px;"></div>
      </section>
      <section class="panel col-6">
        <h3>Trace Explorer</h3>
        <div class="toolbar">
          <button onclick="loadTraces()">Reload Traces</button>
          <select id="traceSelect"></select>
          <button onclick="loadSelectedTrace()">Load Selected Trace</button>
        </div>
        <div id="traceList" class="trace-list"></div>
        <pre id="traceDetails" class="log" style="max-height: 220px; margin-top: 8px;"></pre>
      </section>
    </div>

    <div class="row">
      <section class="panel col-12">
        <h3>Scenario Replay</h3>
        <div class="toolbar">
          <input id="replayRunId" placeholder="run_id" />
          <input id="replayScenarioId" placeholder="scenario id (optional)" />
          <button onclick="replayScenario()">Replay Scenario</button>
        </div>
        <pre id="replayResult" class="log"></pre>
      </section>
    </div>
  </div>

  <script>
    let lastState = {};
    let traces = [];
    let selectedTrace = "";
    let latestReadyPayload = null;

    async function fetchJson(url, options) {
      const response = await fetch(url, options);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || ("Request failed " + response.status));
      }
      return payload;
    }

    function healthBarClass(v) {
      if (v >= 0.95) return "good";
      if (v >= 0.85) return "warn";
      return "bad";
    }

    function buildSpark(values) {
      const normalized = values.slice(-20).map((v) => {
        const safe = Math.max(0, Math.min(1, Number(v || 0)));
        return Math.round(safe * 100);
      });
      while (normalized.length < 20) normalized.unshift(0);
      return `<div class=\"spark\">${normalized.map((v) => `<span style=\"height:${v}px\" title=\"${v}%\"></span>`).join(\"\")}</div>`;
    }

    function renderSummary(state) {
      const evalState = state.last_evaluation || {};
      const decision = evalState.decision || "unknown";
      const risk = state.verification_metrics ? state.verification_metrics.risk_score : "n/a";
      const passRate = state.verification_metrics ? state.verification_metrics.pass_rate : null;
      const trace = state.last_evaluation ? state.last_evaluation.run_id : "-";
      const riskText = typeof risk === "number" ? risk.toFixed(2) : risk;
      const passText = typeof passRate === "number" ? `${Math.round(passRate * 100)}%` : "n/a";
      const decisionClass = decision === "promote" ? "good" : decision === "rollback" ? "bad" : "muted";

      document.getElementById("summaryCards").innerHTML = `
        <div class="summary-card">
          <div class="label">Fleet Nodes</div>
          <div class="value">${state.node_count}</div>
          <div class="muted">With active config: ${state.nodes_with_config}</div>
        </div>
        <div class="summary-card">
          <div class="label">Broker</div>
          <div class="value">${state.broker_mode}</div>
          <div class="muted">Node prefix: ${state.node_prefix || "-"}</div>
        </div>
        <div class="summary-card">
          <div class="label">Canary Evaluation</div>
          <div class="value ${decisionClass}">${decision}</div>
          <div class="muted">Pass Rate: ${passText} · Risk: ${riskText}</div>
        </div>
        <div class="summary-card">
          <div class="label">Latest Dispatch</div>
          <div class="value">${trace}</div>
          <div class="muted">Target nodes: ${(state.last_dispatch && state.last_dispatch.target_nodes ? state.last_dispatch.target_nodes.join(',') : "-")}</div>
        </div>
      `;
      document.getElementById("decisionCard").innerHTML = `
        <div class="decision ${decisionClass}">Decision: ${decision}</div>
        <div>Samples: ${evalState.telemetry_samples_total ?? "-"}</div>
        <div>All nodes applied: ${evalState.all_nodes_applied ?? "-"}</div>
        <div>Telemetry violation: ${evalState.telemetry_violation ?? "-"}</div>
      `;
      document.getElementById("brokerMode").textContent = `broker: ${state.broker_mode}`;
      document.getElementById("fleetConfigured").textContent = `configured: ${state.nodes_with_config}/${state.node_count}`;
      document.getElementById("lastDispatch").textContent = `last dispatch: ${state.last_dispatch?.run_id ?? "-"}`;
    }

    function renderFleet(state) {
      const rows = state.nodes.map((node) => {
        const event = node.last_event || {};
        const lastHealth = node.last_telemetry ? Number(node.last_telemetry.telemetry_health ?? 0).toFixed(3) : "-";
        const statusClass = node.last_event && node.last_event.status ? healthBarClass(node.last_event.status === "accepted" ? 1 : 0.75) : "muted";
        const history = node.telemetry_history || [];
        const sparkVals = history.map((item) => Number(item.telemetry_health || 0).toFixed(2));
        const latestConfig = node.current_config || {};
        const configSampleRate = latestConfig.sampling_rate_hz || "-";
        return `
          <tr>
            <td><strong>${node.node_id}</strong><div class="muted">samples: ${node.telemetry_count}</div></td>
            <td class="${statusClass}">Last: ${lastHealth} ${node.last_telemetry && node.last_telemetry.ts ? `<div class=\"muted\">${node.last_telemetry.ts}</div>` : ""}</td>
            <td>${buildSpark(sparkVals)}</td>
            <td><div>sampling_rate_hz: ${configSampleRate}</div><div class=\"muted\">deployment: ${(latestConfig.deployment || {}).percentage ?? "-"}</div></td>
            <td><div>${event.event || "-"}</div><div class=\"muted\">${event.status || ""} ${event.reason ? `· ${event.reason}` : ""}</div></td>
          </tr>
        `;
      }).join("");
      document.getElementById("fleetTable").innerHTML = rows || `<tr><td colspan=\"5\">No node.</td></tr>`;
    }

    function renderEvents(state) {
      const events = state.events || [];
      const lines = events.slice().reverse().map((entry) => {
        const ts = new Date(entry.ts).toLocaleTimeString();
        return `<div>[${ts}] <strong>${entry.type}</strong> · ${entry.message}</div>`;
      }).join("");
      document.getElementById("eventLog").innerHTML = lines || "No events yet.";
    }

    function renderTraceSelect() {
      const select = document.getElementById("traceSelect");
      select.innerHTML = "";
      traces.forEach((trace) => {
        const option = document.createElement("option");
        option.value = trace.run_id;
        option.textContent = `${trace.run_id} | ${trace.decision || "unknown"} | risk ${trace.risk_score}`;
        select.appendChild(option);
      });
    }

    function renderTraceList() {
      const wrap = document.getElementById("traceList");
      if (!traces.length) {
        wrap.innerHTML = "<div class='trace-item'>No traces found.</div>";
        return;
      }
      wrap.innerHTML = traces.map((trace) => `
        <div class="trace-item ${trace.run_id === selectedTrace ? 'active' : ''}" onclick="pickTrace('${trace.run_id}')">
          <div><strong>${trace.run_id}</strong> · ${trace.decision || "unknown"}</div>
          <div class="muted">scenarios: ${trace.scenario_count || 0}, failed: ${trace.failed_cases || 0}, pass rate: ${trace.pass_rate || 0}</div>
          <div class="muted">${trace.created_at || "-"}</div>
        </div>
      `).join("");
    }

    function pickTrace(runId) {
      selectedTrace = runId;
      document.getElementById("replayRunId").value = runId;
      renderTraceList();
      loadTraceById(runId);
    }

    async function refreshState() {
      const [state, events] = await Promise.all([
        fetchJson("/api/state"),
        fetchJson("/api/events"),
      ]);
      state.events = events;
      lastState = state;
      if (!state.last_dispatch && !state.last_evaluation && !state.events.length) {
        // warm state while waiting
      }
      renderSummary(state);
      renderFleet(state);
      renderEvents(state);
    }

    async function refreshTraces() {
      traces = await fetchJson("/api/traces");
      renderTraceSelect();
      renderTraceList();
    }

    async function loadTraceById(runId) {
      const trace = await fetchJson(`/api/trace/${encodeURIComponent(runId)}`);
      document.getElementById("traceDetails").textContent = JSON.stringify(trace, null, 2);
      document.getElementById("replayRunId").value = runId;
    }

    async function loadSelectedTrace() {
      const el = document.getElementById("traceSelect");
      if (!el.value) {
        return;
      }
      selectedTrace = el.value;
      await loadTraceById(selectedTrace);
    }

    async function loadTraces() {
      try {
        await refreshTraces();
      } catch (error) {
        document.getElementById("traceDetails").textContent = String(error);
      }
    }

    async function submitDispatch() {
      let payload;
      try {
        payload = JSON.parse(document.getElementById("payload").value);
      } catch (err) {
        document.getElementById("dispatchState").textContent = "invalid payload JSON";
        return;
      }
      const percentage = Number(document.getElementById("percentage").value);
      const telemetrySamples = Number(document.getElementById("telemetrySamples").value);
      payload.run_id = document.getElementById("run_id").value || payload.run_id || ("web_" + Date.now());
      try {
        const result = await fetchJson("/api/dispatch", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            ready_payload: payload,
            percentage: percentage,
            telemetry_samples_per_node: telemetrySamples,
          }),
        });
        document.getElementById("dispatchResult").textContent = JSON.stringify(result, null, 2);
        document.getElementById("dispatchState").textContent = "dispatched";
        await refreshState();
      } catch (err) {
        document.getElementById("dispatchResult").textContent = String(err);
        document.getElementById("dispatchState").textContent = "failed";
      }
    }

    async function runOperatorPlan() {
      const prompt = document.getElementById("operatorPrompt").value;
      const plannerMode = document.getElementById("plannerMode").value;
      const scenarioCount = Number(document.getElementById("operatorScenarioCount").value);
      const workers = Number(document.getElementById("operatorWorkers").value);
      const adaptive = document.getElementById("operatorAdaptive").value === "true";
      document.getElementById("operatorState").textContent = "running...";
      document.getElementById("operatorResult").textContent = "Generating plan, running schema gate, verification matrix, and trace save...";

      try {
        const result = await fetchJson("/api/operator/run", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            prompt,
            planner_mode: plannerMode,
            scenario_count: scenarioCount,
            workers,
            adaptive,
            suggest_settings: true,
          }),
        });
        latestReadyPayload = result.ready_payload || null;
        document.getElementById("operatorResult").textContent = JSON.stringify(result, null, 2);
        document.getElementById("operatorState").textContent = result.ready_payload ? "ready for canary" : "blocked";
        if (latestReadyPayload) {
          document.getElementById("payload").value = JSON.stringify(latestReadyPayload, null, 2);
          document.getElementById("run_id").value = latestReadyPayload.run_id;
          document.getElementById("percentage").value = latestReadyPayload.plan.deployment.percentage;
        }
        await refreshAll();
      } catch (err) {
        latestReadyPayload = null;
        document.getElementById("operatorResult").textContent = String(err);
        document.getElementById("operatorState").textContent = "failed";
      }
    }

    async function deployVerifiedPlan() {
      if (!latestReadyPayload) {
        try {
          latestReadyPayload = JSON.parse(document.getElementById("payload").value);
        } catch (err) {
          document.getElementById("operatorState").textContent = "no verified payload";
          return;
        }
      }
      document.getElementById("payload").value = JSON.stringify(latestReadyPayload, null, 2);
      await submitDispatch();
      document.getElementById("operatorState").textContent = "dispatch submitted";
    }

    async function replayScenario() {
      const runId = document.getElementById("replayRunId").value;
      const scenarioId = document.getElementById("replayScenarioId").value;
      if (!runId) {
        document.getElementById("replayResult").textContent = "run_id required";
        return;
      }
      try {
        const result = await fetchJson("/api/replay", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            run_id: runId,
            scenario_id: scenarioId || undefined,
          }),
        });
        document.getElementById("replayResult").textContent = JSON.stringify(result, null, 2);
      } catch (err) {
        document.getElementById("replayResult").textContent = String(err);
      }
    }

    async function refreshAll() {
      await Promise.all([refreshState(), refreshTraces()]);
    }

    setInterval(() => {
      refreshState();
    }, 1500);
    setInterval(() => {
      refreshTraces();
    }, 4000);
    refreshAll();
  </script>
</body>
</html>
"""


@dataclass
class FleetController:
    node_count: int
    broker_mode: str
    telemetry_interval: float
    broker_host: str
    broker_port: int
    telemetry_samples_per_node: int
    trace_dir: Path
    node_prefix: str = "node-"
    node_id_width: int = 2
    nodes: list[EdgeNode] = field(default_factory=list)
    last_dispatch: dict[str, Any] | None = None
    last_evaluation: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    last_operator_result: dict[str, Any] | None = None
    last_event_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        self.node_ids = [f"{self.node_prefix}{index:0{self.node_id_width}d}" for index in range(1, self.node_count + 1)]
        self.nodes = self._create_nodes()
        self._start_telemetry_loops()

    def _create_nodes(self) -> list[EdgeNode]:
        if self.broker_mode == "in-memory":
            broker = InMemoryBroker()
            nodes = [EdgeNode(node_id=node_id, broker=broker) for node_id in self.node_ids]
        else:
            try:
                transport = PahoMqttTransport(
                    broker_host=self.broker_host,
                    broker_port=self.broker_port,
                )
                nodes = [EdgeNode(node_id=node_id, broker=transport) for node_id in self.node_ids]
            except RuntimeTransportUnavailable as exc:
                raise RuntimeError(str(exc))

        for node in nodes:
            node.connect()
        return nodes

    def _append_event(self, event_type: str, message: str, details: dict[str, Any] | None = None) -> None:
        with self.lock:
            self.events.append(
                {
                    "ts": time.time(),
                    "type": event_type,
                    "message": message,
                    "details": details or {},
                },
            )
            if len(self.events) > 200:
                self.events = self.events[-200:]

    def _start_telemetry_loops(self) -> None:
        for node in self.nodes:
            def _worker(target_node: EdgeNode = node) -> None:
                while True:
                    sample = target_node.publish_telemetry(1.0)
                    self._append_event(
                        "telemetry",
                        f"{target_node.node_id} baseline telemetry: {sample.get('telemetry_health')}",
                        {"node_id": target_node.node_id, "telemetry_health": sample.get("telemetry_health")},
                    )
                    time.sleep(max(0.5, self.telemetry_interval))
            threading.Thread(target=_worker, daemon=True).start()

    @property
    def state(self) -> dict[str, Any]:
        with self.lock:
            nodes_summary = []
            for node in self.nodes:
                telemetry_history = [
                    {
                        "telemetry_health": sample.get("telemetry_health"),
                        "ts": sample.get("ts"),
                    }
                    for sample in node.telemetry_history[-20:]
                ]
                nodes_summary.append({
                    "node_id": node.node_id,
                    "telemetry_count": len(node.telemetry_history),
                    "telemetry_history": telemetry_history,
                    "last_telemetry": node.telemetry_history[-1] if node.telemetry_history else None,
                    "current_config": node.current_config,
                    "last_event": node.last_event(),
                })
            return {
                "nodes": nodes_summary,
                "node_count": self.node_count,
                "node_prefix": self.node_prefix,
                "broker_mode": self.broker_mode,
                "nodes_with_config": sum(1 for node in self.nodes if node.current_config is not None),
                "last_dispatch": self.last_dispatch,
                "last_evaluation": self.last_evaluation,
                "telemetry_samples_per_node": self.telemetry_samples_per_node,
                "verification_metrics": self._verification_metrics(),
                "last_operator_result": self.last_operator_result,
                "events": self.events[-60:],
            }

    def node_events(self) -> list[dict[str, Any]]:
        with self.lock:
            return self.events[-120:]

    def _verification_metrics(self) -> dict[str, Any]:
        if self.last_evaluation is None:
            return {}
        return {
            "pass_rate": self.last_evaluation.get("pass_rate"),
            "decision": self.last_evaluation.get("decision"),
            "risk_score": self.last_evaluation.get("risk_score"),
        }

    def run_operator_plan(
        self,
        prompt: str,
        *,
        planner_mode: str = "openai",
        scenario_count: int = 50,
        workers: int = DEFAULT_ADAPTIVE_WORKERS,
        adaptive: bool = True,
        adaptive_rounds: int = 1,
        adaptive_budget: int = 20,
        suggest_settings: bool = True,
    ) -> dict[str, Any]:
        prompt = (prompt or DEFAULT_OPERATOR_PROMPT).strip()
        scenario_count = max(5, min(500, int(scenario_count)))
        workers = max(1, min(16, int(workers)))

        self._append_event(
            "operator_start",
            f"Planning via {planner_mode}; scenarios={scenario_count}; adaptive={adaptive}",
            {"planner_mode": planner_mode, "scenario_count": scenario_count},
        )

        client: PlanClient
        if planner_mode == "demo":
            client = DemoPlanClient()
        elif planner_mode == "openai":
            client = OpenAIResponsesPlanClient()
        else:
            raise RuntimeError("planner_mode must be 'openai' or 'demo'")

        harness = run_harness(prompt, client, run_id=make_run_id())
        payload: dict[str, Any] = {
            "prompt": prompt,
            "planner_mode": planner_mode,
            "harness": harness.to_dict(),
        }

        if harness.deployment_decision != "ready_for_canary" or harness.plan is None:
            payload["ready_payload"] = None
            self._record_operator_result(payload, "operator_blocked", "Operator plan blocked before verification.")
            return payload

        plan = OptimizationPlan.from_dict(harness.plan)
        scenarios = generate_scenario_matrix(count=scenario_count, seed_start=1)
        report = run_verification_matrix(
            plan=plan,
            scenarios=scenarios,
            enable_adaptive=adaptive,
            workers=workers,
            adaptive_rounds=adaptive_rounds,
            adaptive_budget=adaptive_budget,
            seed_start=1,
        )

        setting_suggestion_report = None
        if suggest_settings:
            setting_suggestion_report = suggest_setting_adjustments(plan=plan, report=report)

        executed_scenarios = (
            tuple(ScenarioSpec(**spec) for spec in report.executed_scenarios)
            if report.executed_scenarios
            else tuple(scenarios)
        )
        trace = build_verification_trace(
            plan=plan,
            report=report,
            scenarios=executed_scenarios,
            run_id=harness.run_id,
            model=os.getenv("OPENAI_MODEL", "gpt-5.5") if planner_mode == "openai" else "demo",
            prompt=prompt,
            setting_suggestion=setting_suggestion_report,
        )
        trace_path = self.trace_dir / f"{trace.run_id}.json"
        save_trace(trace, trace_path)

        ready_payload = None
        if report.decision == "ready_for_canary":
            ready_payload = {
                "run_id": trace.run_id,
                "plan": trace.plan,
                "verification": report.to_dict(),
                "trace": {"run_id": trace.run_id, "path": str(trace_path)},
            }
            if setting_suggestion_report is not None:
                ready_payload["setting_suggestions"] = setting_suggestion_report.to_dict()

        payload.update(
            {
                "verification": report.to_dict(),
                "setting_suggestions": (
                    setting_suggestion_report.to_dict() if setting_suggestion_report else None
                ),
                "trace": {"run_id": trace.run_id, "path": str(trace_path)},
                "ready_payload": ready_payload,
            }
        )
        event_type = "operator_ready" if ready_payload else "operator_blocked"
        message = (
            f"Operator run {trace.run_id}: {report.decision}, risk={report.risk_score:.3f}, "
            f"pass_rate={report.pass_rate:.3f}"
        )
        self._record_operator_result(payload, event_type, message)
        return payload

    def _record_operator_result(self, payload: dict[str, Any], event_type: str, message: str) -> None:
        with self.lock:
            self.last_operator_result = payload
        self._append_event(event_type, message, {"run_id": payload.get("harness", {}).get("run_id")})

    def run_dispatch(self, ready_payload: dict[str, Any], percentage: float) -> dict[str, Any]:
        with self.lock:
            verification = ready_payload.get("verification", {})
            if verification.get("decision") != "ready_for_canary":
                raise RuntimeError("ready_payload must have verification.decision='ready_for_canary'")
            if percentage <= 0 or percentage > 100:
                raise RuntimeError("percentage must be between 1 and 100")

            payload = dict(ready_payload)
            if "run_id" not in payload:
                payload["run_id"] = f"web_{int(time.time())}"
            payload["plan"]["deployment"]["percentage"] = percentage
            config = build_ota_config(payload)

            broker = self.nodes[0].broker
            if broker is None:
                raise RuntimeError("No broker attached to nodes")

            self._append_event(
                "dispatch_start",
                f"Dispatching canary run_id={payload['run_id']} percentage={percentage}%",
                {"run_id": payload["run_id"]},
            )
            report = dispatch_to_canary(
                broker=broker,
                config=config,
                node_ids=self.node_ids,
                percentage=percentage,
                run_id=payload.get("run_id"),
            )

            target_nodes = set(report["target_nodes"])
            for node in self.nodes:
                if node.node_id not in target_nodes:
                    continue
                for _ in range(max(0, self.telemetry_samples_per_node)):
                    if node.current_config is None:
                        # Give callback loop time to apply config.
                        time.sleep(0.05)
                    if node.current_config is None:
                        continue
                    node.publish_telemetry(float(node.current_config["rollback"]["min_telemetry_health"]) + 0.01)

            evaluation = evaluate_canary_dispatch(
                report,
                self.nodes,
                telemetry_health_floor=float(config.rollback["min_telemetry_health"]),
            )
            self.last_dispatch = report
            self.last_evaluation = evaluation
            self._append_event(
                "dispatch_complete",
                f"Decision: {evaluation.get('decision')} for run_id={evaluation.get('run_id')}",
                evaluation,
            )
            return {"dispatch": report, "evaluation": evaluation}

    def list_traces(self) -> list[dict[str, Any]]:
        if not self.trace_dir.exists():
            return []
        results: list[dict[str, Any]] = []
        for path in sorted(self.trace_dir.glob("*.json")):
            try:
                trace = load_trace(path)
            except Exception:
                continue
            scenario_records = list(trace.scenario_records)
            failed_records = [r for r in scenario_records if not r["result"].get("accepted", True)]
            pass_rate = trace.verification.get("pass_rate")
            decision = trace.verification.get("decision")
            risk_score = trace.verification.get("risk_score")
            results.append({
                "run_id": trace.run_id,
                "created_at": trace.created_at,
                "path": str(path),
                "scenario_count": len(scenario_records),
                "failed_cases": len(failed_records),
                "pass_rate": pass_rate,
                "risk_score": risk_score,
                "decision": decision,
            })
        results.sort(key=lambda item: item["created_at"], reverse=True)
        return results

    def get_trace(self, run_id: str) -> tuple[Any, Path]:
        if not run_id:
            raise KeyError("run_id is required")
        prefix_matches: list[tuple[Any, Path]] = []
        for path in sorted(self.trace_dir.glob("*.json")):
            try:
                trace = load_trace(path)
            except Exception:
                continue

            if trace.run_id == run_id or path.stem == run_id:
                return trace, path
            if trace.run_id.startswith(f"{run_id}_") or trace.run_id.startswith(run_id):
                prefix_matches.append((trace, path))

        if len(prefix_matches) == 1:
            return prefix_matches[0]
        if len(prefix_matches) > 1:
            raise KeyError(f"multiple traces match run_id prefix: {run_id}")
        raise KeyError(f"run_id not found: {run_id}")

    def get_trace_detail(self, run_id: str) -> dict[str, Any]:
        trace, _ = self.get_trace(run_id)
        trace_dict = trace.to_dict()
        summary_records = trace_dict.get("scenario_records", [])
        failed = [
            {
                "scenario_id": rec["scenario"]["scenario_id"],
                "accepted": rec["result"].get("accepted", True),
                "reason": rec["result"].get("reason"),
                "failure_count": len(rec["result"].get("failed_invariants", [])),
            }
            for rec in summary_records
        ]
        return {
            **trace_dict,
            "scenario_count": len(summary_records),
            "failed_cases": [entry for entry in failed if not entry["accepted"]],
            "failed_count": len([entry for entry in failed if not entry["accepted"]]),
        }

    def replay_trace(self, run_id: str, scenario_id: str | None = None) -> dict[str, Any]:
        trace, _ = self.get_trace(run_id)
        if not trace.scenario_records:
            raise RuntimeError(f"trace has no scenarios: {run_id}")

        target_scenario_id = scenario_id
        if target_scenario_id is None:
            target_scenario_id = trace.scenario_records[0]["scenario"]["scenario_id"]
        return replay_trace_case(trace=trace, scenario_id=target_scenario_id)


class DashboardHandler(BaseHTTPRequestHandler):
    controller: FleetController

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send_html(INDEX_HTML)
            return
        if parsed.path == "/api/state":
            self._send_json(self.controller.state)
            return
        if parsed.path == "/api/events":
            self._send_json(self.controller.node_events())
            return
        if parsed.path == "/api/traces":
            self._send_json(self.controller.list_traces())
            return

        if parsed.path.startswith("/api/trace/"):
            run_id = parsed.path.replace("/api/trace/", "", 1)
            if not run_id:
                self._send_json({"error": "run_id required"}, status=400)
                return
            try:
                self._send_json(self.controller.get_trace_detail(run_id))
            except KeyError as exc:
                self._send_json({"error": str(exc)}, status=404)
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else "{}"

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            request = {}

        if parsed.path == "/api/dispatch":
            try:
                ready_payload = request["ready_payload"]
                percentage = float(request.get("percentage", ready_payload["plan"]["deployment"]["percentage"]))
                telemetry_samples = int(request.get("telemetry_samples_per_node", 1))
                if telemetry_samples >= 0:
                    self.controller.telemetry_samples_per_node = telemetry_samples

                result = self.controller.run_dispatch(ready_payload, percentage=percentage)
                self._send_json(result)
            except (KeyError, TypeError, ValueError) as exc:
                self._send_json({"error": f"invalid request body: {exc}"}, status=400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if parsed.path == "/api/operator/run":
            try:
                result = self.controller.run_operator_plan(
                    prompt=str(request.get("prompt") or DEFAULT_OPERATOR_PROMPT),
                    planner_mode=str(request.get("planner_mode") or "openai"),
                    scenario_count=int(request.get("scenario_count", 50)),
                    workers=int(request.get("workers", DEFAULT_ADAPTIVE_WORKERS)),
                    adaptive=bool(request.get("adaptive", True)),
                    adaptive_rounds=int(request.get("adaptive_rounds", 1)),
                    adaptive_budget=int(request.get("adaptive_budget", 20)),
                    suggest_settings=bool(request.get("suggest_settings", True)),
                )
                self._send_json(result)
            except (KeyError, TypeError, ValueError) as exc:
                self._send_json({"error": f"invalid request body: {exc}"}, status=400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if parsed.path == "/api/replay":
            try:
                run_id = request.get("run_id")
                if not run_id:
                    raise KeyError("run_id")
                scenario_id = request.get("scenario_id")
                if scenario_id:
                    scenario_id = str(scenario_id)
                replay = self.controller.replay_trace(run_id, scenario_id=scenario_id)
                self._send_json(replay)
            except KeyError as exc:
                self._send_json({"error": f"missing field: {exc}"}, status=400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        self._send_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def main() -> None:
    load_env_file()
    parser = argparse.ArgumentParser(description="Sprint 7 web dashboard for runtime visualization.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--node-count", type=int, default=5)
    parser.add_argument("--telemetry-interval", type=float, default=2.0)
    parser.add_argument("--broker-mode", choices=["in-memory", "mqtt"], default="in-memory")
    parser.add_argument("--broker-host", default="localhost")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--node-prefix", default="node-")
    parser.add_argument("--node-id-width", type=int, default=2)
    parser.add_argument("--trace-dir", default=".swarmforge_traces")

    args = parser.parse_args()

    try:
        controller = FleetController(
            node_count=args.node_count,
            broker_mode=args.broker_mode,
            telemetry_interval=args.telemetry_interval,
            broker_host=args.broker_host,
            broker_port=args.broker_port,
            telemetry_samples_per_node=1,
            node_prefix=args.node_prefix,
            node_id_width=args.node_id_width,
            trace_dir=Path(args.trace_dir),
        )
    except Exception as exc:
        print(f"Failed to initialize Sprint 7 dashboard: {exc}", file=sys.stderr)
        raise SystemExit(1)

    DashboardHandler.controller = controller
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)

    def _shutdown(_: int, __: object | None = None) -> None:
        server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"SwarmForge Sprint 7 dashboard on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
