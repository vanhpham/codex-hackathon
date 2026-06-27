from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.edge_runtime import EdgeNode, InMemoryBroker, dispatch_to_canary, evaluate_canary_dispatch
from swarmforge.mqtt_transport import MosquittoDockerTransport, RuntimeTransportUnavailable
from swarmforge.ota import build_ota_config

INDEX_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>SwarmForge Sprint 6 Dashboard</title>
  <style>
    body { font-family: Inter, system-ui, sans-serif; margin: 24px; max-width: 1100px; }
    h1 { margin-top: 0; }
    .panel { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
    pre { background: #f5f5f5; padding: 8px; border-radius: 6px; overflow: auto; }
    button, input, textarea { font: inherit; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .row { margin-top: 8px; }
    .muted { color: #666; font-size: 0.95rem; }
  </style>
</head>
<body>
  <h1>SwarmForge Sprint 6</h1>
  <p>Run verification-ready payloads through a bounded MQTT canary runtime.</p>
  <div class="grid">
    <div class="panel">
      <h3>Fleet State</h3>
      <pre id="state">Loading...</pre>
      <button onclick="refreshState()">Refresh</button>
    </div>
    <div class="panel">
      <h3>Node Events</h3>
      <pre id="events">[]</pre>
      <button onclick="refreshState()">Refresh</button>
    </div>
  </div>
  <div class="panel">
    <h3>Dispatch</h3>
    <form id="dispatchForm">
      <div class="row">Run ID: <input id="run_id" value="run_manual_001" /></div>
      <div class="row">Plan percentage: <input id="percentage" type="number" min="1" max="20" value="5" /></div>
      <div class="row">Health samples per target node: <input id="telemetrySamples" type="number" min="0" max="10" value="1" /></div>
      <div class="row">Request body:
        <textarea id="payload" rows="14" cols="110">
{"run_id":"run_manual_001","plan":{"intent":"reduce_noise_and_bandwidth","target_metric":"accelerometer","sampling_rate_hz":2,"log_level":"WARNING","filter":{"type":"median","window_size":5},"telemetry_collection":{"metrics":["accelerometer","temperature","battery"],"aggregation_window_seconds":5,"publish_mode":"summary_and_anomalies","max_payload_kbps":8},"deployment":{"strategy":"canary","percentage":5,"observation_window_seconds":10},"rollback":{"enabled":true,"max_latency_ms":250,"max_error_rate":0.02,"min_telemetry_health":0.95}},"verification":{"decision":"ready_for_canary","risk_score":0.1}}
        </textarea>
      </div>
      <div class="row"><button type="button" onclick="submitDispatch()">Dispatch Canary</button></div>
    </form>
    <pre id="dispatchResult" class="muted">No dispatch yet</pre>
  </div>
  <script>
    async function refreshState() {
      const [stateRes, eventsRes] = await Promise.all([
        fetch('/api/state'),
        fetch('/api/events'),
      ]);
      const state = await stateRes.json();
      const events = await eventsRes.json();
      document.getElementById('state').textContent = JSON.stringify(state, null, 2);
      document.getElementById('events').textContent = JSON.stringify(events, null, 2);
    }
    async function submitDispatch() {
      let payload;
      try {
        payload = JSON.parse(document.getElementById('payload').value);
      } catch (err) {
        document.getElementById('dispatchResult').textContent = "Invalid JSON payload";
        return;
      }
      const percentage = Number(document.getElementById('percentage').value);
      const telemetrySamples = Number(document.getElementById('telemetrySamples').value);
      payload.run_id = document.getElementById('run_id').value || payload.run_id || ("web_" + Date.now());
      const res = await fetch('/api/dispatch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          ready_payload: payload,
          percentage: percentage,
          telemetry_samples_per_node: telemetrySamples,
        }),
      });
      const data = await res.json();
      document.getElementById('dispatchResult').textContent = JSON.stringify(data, null, 2);
      await refreshState();
    }
    setInterval(refreshState, 2000);
    refreshState();
  </script>
</body>
</html>
"""


class FleetController:
    def __init__(
        self,
        node_count: int,
        broker_mode: str,
        telemetry_interval: float,
        broker_host: str,
        broker_port: int,
        telemetry_samples_per_node: int,
        node_prefix: str = "node-",
        node_id_width: int = 2,
    ) -> None:
        self.node_count = node_count
        self.broker_mode = broker_mode
        self.telemetry_interval = telemetry_interval
        self.telemetry_samples_per_node = telemetry_samples_per_node
        self.node_prefix = node_prefix
        self.lock = threading.Lock()
        self.node_ids = [
            f"{node_prefix}{index:0{node_id_width}d}" for index in range(1, node_count + 1)
        ]
        self.last_dispatch: dict[str, Any] | None = None
        self.last_evaluation: dict[str, Any] | None = None
        self.nodes = self._create_nodes(broker_host, broker_port)
        self._start_telemetry_loops()

    def _create_nodes(self, broker_host: str, broker_port: int) -> list[EdgeNode]:
        if self.broker_mode == "in-memory":
            broker = InMemoryBroker()
            return [EdgeNode(node_id=node_id, broker=broker) for node_id in self.node_ids]

        try:
            transport = MosquittoDockerTransport(
                broker_host=broker_host,
                broker_port=broker_port,
            )
            return [EdgeNode(node_id=node_id, broker=transport) for node_id in self.node_ids]
        except RuntimeTransportUnavailable as exc:
            raise RuntimeError(str(exc))

    def _start_telemetry_loops(self) -> None:
        for node in self.nodes:
            node.connect()

            def _worker(target_node: EdgeNode = node) -> None:
                while True:
                    target_node.publish_telemetry(1.0)
                    time.sleep(max(0.5, self.telemetry_interval))

            threading.Thread(target=_worker, daemon=True).start()

    @property
    def state(self) -> dict[str, Any]:
        with self.lock:
            return {
                "nodes": [
                    {
                        "node_id": node.node_id,
                        "telemetry_count": len(node.telemetry_history),
                        "last_telemetry": node.telemetry_history[-1] if node.telemetry_history else None,
                        "current_config": node.current_config,
                        "last_event": node.last_event(),
                    }
                    for node in self.nodes
                ],
                "node_count": self.node_count,
                "broker_mode": self.broker_mode,
                "nodes_with_config": sum(1 for node in self.nodes if node.current_config is not None),
                "last_dispatch": self.last_dispatch,
                "last_evaluation": self.last_evaluation,
                "telemetry_samples_per_node": self.telemetry_samples_per_node,
            }

    def node_events(self) -> list[dict[str, Any]]:
        with self.lock:
            events: list[dict[str, Any]] = []
            for node in self.nodes:
                events.extend(node.event_history[-2:])
            return events[-100:]

    def run_dispatch(self, ready_payload: dict[str, Any], percentage: float) -> dict[str, Any]:
        with self.lock:
            verification = ready_payload.get("verification", {})
            if verification.get("decision") != "ready_for_canary":
                raise RuntimeError(
                    "ready_payload must have verification.decision='ready_for_canary'"
                )

            payload = dict(ready_payload)
            if "run_id" not in payload:
                payload["run_id"] = f"web_{int(time.time())}"
            payload["plan"]["deployment"]["percentage"] = percentage
            config = build_ota_config(payload)

            broker = self.nodes[0].broker
            if broker is None:
                raise RuntimeError("No broker attached to nodes")

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
                        # Give transport callback loop a moment to apply config.
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
            return {"dispatch": report, "evaluation": evaluation}


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
        elif parsed.path == "/api/state":
            self._send_json(self.controller.state)
        elif parsed.path == "/api/events":
            self._send_json(self.controller.node_events())
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/dispatch":
            self._send_json({"error": "not found"}, status=404)
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            request = json.loads(body)
            ready_payload = request["ready_payload"]
            percentage = float(request.get("percentage", ready_payload["plan"]["deployment"]["percentage"]))
            telemetry_samples = int(request.get("telemetry_samples_per_node", 1))
            if telemetry_samples >= 0:
                self.controller.telemetry_samples_per_node = telemetry_samples

            result = self.controller.run_dispatch(ready_payload, percentage=percentage)
            self._send_json(result)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            self._send_json({"error": f"invalid request body: {exc}"}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 6 web dashboard for canary runtime.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--node-count", type=int, default=5)
    parser.add_argument("--telemetry-interval", type=float, default=2.0)
    parser.add_argument("--broker-mode", choices=["in-memory", "mqtt"], default="in-memory")
    parser.add_argument("--broker-host", default="localhost")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--node-prefix", default="node-")
    parser.add_argument("--node-id-width", type=int, default=2)

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
        )
    except Exception as exc:
        print(f"Failed to initialize Sprint 6 dashboard: {exc}", file=sys.stderr)
        raise SystemExit(1)

    DashboardHandler.controller = controller
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)

    def _shutdown(_: int, __: object | None = None) -> None:
        server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"SwarmForge Sprint 6 dashboard on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if args.broker_mode == "mqtt":
            for node in controller.nodes:
                if node.broker is not None and hasattr(node.broker, "close"):
                    node.broker.close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
