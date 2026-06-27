from __future__ import annotations

import argparse
import json
import random
import signal
import threading
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.edge_runtime import EdgeNode
from swarmforge.mqtt_transport import PahoMqttTransport, RuntimeTransportUnavailable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _emit_event(kind: str, payload: dict) -> None:
    envelope = {
        "ts": _utc_now(),
        "kind": kind,
        "payload": payload,
    }
    print(json.dumps(envelope, sort_keys=True))


def _telemetry_floor_from_node(node: EdgeNode) -> float:
    config = node.current_config
    if not config:
        return 1.0
    try:
        return float(config["rollback"]["min_telemetry_health"])
    except Exception:
        return 1.0


def _health_generator(current_floor: float) -> float:
    jitter = random.uniform(-0.03, 0.03)
    return min(1.0, max(0.6, current_floor + jitter + random.uniform(0.0, 0.04)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one edge node connected to MQTT OTA topics.")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--broker-host", default="localhost")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--telemetry-interval", type=float, default=1.0)
    parser.add_argument("--health-curve", choices=["healthy", "steady", "noisy"], default="healthy")
    parser.add_argument(
        "--health-floor",
        type=float,
        default=0.95,
        help="Minimum telemetry health for synthetic baseline floor",
    )
    args = parser.parse_args()

    stop_event = threading.Event()

    def stop(_: int, __: object | None = None) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        transport = PahoMqttTransport(
            broker_host=args.broker_host,
            broker_port=args.broker_port,
        )
        node = EdgeNode(args.node_id, broker=transport)
        node.connect()
    except RuntimeTransportUnavailable as exc:
        _emit_event("fatal", {"message": str(exc)})
        raise SystemExit(2)

    config_path = Path("/tmp") / f"swarmforge-node-{args.node_id}.json"

    def _status_publisher() -> None:
        while not stop_event.is_set():
            floor = min(args.health_floor, _telemetry_floor_from_node(node))
            if args.health_curve == "healthy":
                health = max(floor, 1.0 + random.uniform(-0.02, 0.01))
            elif args.health_curve == "steady":
                health = floor + 0.01
            else:
                health = _health_generator(floor)

            sample = node.publish_telemetry(health)
            config_path.write_text(json.dumps(sample, sort_keys=True), encoding="utf-8")
            _emit_event("telemetry", sample)
            time.sleep(max(0.2, args.telemetry_interval))

    publisher = threading.Thread(target=_status_publisher, daemon=True)
    publisher.start()

    _emit_event("ready", {"node_id": args.node_id})
    while not stop_event.is_set():
        last = node.last_event()
        if last:
            _emit_event("event", {"node_id": args.node_id, "event": last})
        node.config_history[:] = []
        node.event_history[:] = []
        time.sleep(0.2)

    transport.close()


if __name__ == "__main__":
    main()
