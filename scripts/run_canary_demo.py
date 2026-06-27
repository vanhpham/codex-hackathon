from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.edge_runtime import EdgeNode, InMemoryBroker, dispatch_to_canary, evaluate_canary_dispatch
from swarmforge.ota import DispatchBlocked, build_ota_config
from swarmforge.traces import load_trace


SAMPLE_PLAN = {
    "intent": "reduce_noise_and_bandwidth",
    "target_metric": "accelerometer",
    "sampling_rate_hz": 2,
    "log_level": "WARNING",
    "filter": {
        "type": "median",
        "window_size": 5,
    },
    "telemetry_collection": {
        "metrics": ["accelerometer", "temperature", "battery"],
        "aggregation_window_seconds": 5,
        "publish_mode": "summary_and_anomalies",
        "max_payload_kbps": 8,
    },
    "deployment": {
        "strategy": "canary",
        "percentage": 5,
        "observation_window_seconds": 10,
    },
    "rollback": {
        "enabled": True,
        "max_latency_ms": 250,
        "max_error_rate": 0.02,
        "min_telemetry_health": 0.95,
    },
}


def expand_health_inputs(values: list[float], count: int) -> list[float]:
    if count <= 0:
        return []
    if not values:
        return [1.0 for _ in range(count)]
    if len(values) == 1:
        return [float(values[0]) for _ in range(count)]
    if len(values) >= count:
        return [float(value) for value in values[:count]]
    expanded = [float(value) for value in values]
    expanded.extend(expanded[-1:] * (count - len(expanded)))
    return expanded


def make_node_ids(count: int, prefix: str = "node-", width: int = 2) -> list[str]:
    return [f"{prefix}{index:0{width}d}" for index in range(1, count + 1)]


def prepare_ready_payload(path: str | None = None, trace_path: str | None = None) -> dict[str, Any]:
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if trace_path is not None:
        return _from_trace(Path(trace_path))

    return {
        "run_id": "demo_0001",
        "plan": SAMPLE_PLAN,
        "verification": {"decision": "ready_for_canary", "risk_score": 0.1},
    }


def _from_trace(path: Path) -> dict[str, Any]:
    trace = load_trace(path)
    return {
        "run_id": trace.run_id,
        "plan": trace.plan,
        "verification": {
            "decision": trace.verification.get("decision", "blocked"),
            "risk_score": trace.verification.get("risk_score", 1.0),
        },
    }


def run_canary_demo(
    ready_payload: dict[str, Any],
    node_count: int,
    *,
    node_prefix: str = "node-",
    node_id_width: int = 2,
    plan_percentage: float | None = None,
    health_values: list[float] | None = None,
) -> dict[str, Any]:
    try:
        config = build_ota_config(ready_payload)
        ready_payload = dict(ready_payload)
        ready_payload["ota"] = config.to_dict()
        if not isinstance(ready_payload.get("plan"), dict):
            raise DispatchBlocked("plan must be an object in ready payload")
    except Exception as exc:
        raise DispatchBlocked(f"ready_payload is not canary-safe: {exc}") from exc

    percentage = (
        plan_percentage
        if plan_percentage is not None
        else float(ready_payload["plan"]["deployment"]["percentage"])
    )

    broker = InMemoryBroker()
    node_ids = make_node_ids(node_count, prefix=node_prefix, width=node_id_width)
    nodes = [EdgeNode(node_id=node_id).attach_bus(broker) for node_id in node_ids]
    for node in nodes:
        node.connect()

    dispatch_report = dispatch_to_canary(
        broker=broker,
        config=config,
        node_ids=node_ids,
        percentage=percentage,
        run_id=ready_payload.get("run_id"),
    )

    targeted_nodes = list(dispatch_report["target_nodes"])
    health_by_node = expand_health_inputs(health_values or [], len(targeted_nodes))
    selected_node_map = {node.node_id: node for node in nodes}

    for node_id, health in zip(targeted_nodes, health_by_node):
        selected_node_map[node_id].publish_telemetry(health)

    evaluation = evaluate_canary_dispatch(
        dispatch_report,
        nodes=nodes,
        telemetry_health_floor=float(config.rollback["min_telemetry_health"]),
    )
    evaluation["telemetry_input"] = {
        node_id: health for node_id, health in zip(targeted_nodes, health_by_node)
    }
    evaluation["config_version"] = config.config_version
    evaluation["source_run_id"] = config.source_run_id

    return {
        "ready_payload": ready_payload,
        "dispatch": dispatch_report,
        "evaluation": evaluation,
        "broker_messages": broker.published_messages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a local canary loop demo from a canary-safe payload.",
    )
    parser.add_argument(
        "--ready-payload",
        help="Path to a ready payload JSON file (decision/plan/ota).",
    )
    parser.add_argument("--trace", help="Load a trace JSON and derive a canary-ready payload.")
    parser.add_argument("--node-count", type=int, default=10)
    parser.add_argument("--node-prefix", default="node-")
    parser.add_argument("--node-id-width", type=int, default=2)
    parser.add_argument("--plan-percentage", type=float, default=None)
    parser.add_argument(
        "--telemetry-health",
        nargs="*",
        type=float,
        default=None,
        help="Optional per-node telemetry health values. Missing values default to 1.0.",
    )
    args = parser.parse_args()

    ready_payload = prepare_ready_payload(
        path=args.ready_payload,
        trace_path=args.trace,
    )

    try:
        result = run_canary_demo(
            ready_payload=ready_payload,
            node_count=args.node_count,
            node_prefix=args.node_prefix,
            node_id_width=args.node_id_width,
            plan_percentage=args.plan_percentage,
            health_values=args.telemetry_health or [],
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    except DispatchBlocked as exc:
        print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
