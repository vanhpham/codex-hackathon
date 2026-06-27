from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from swarmforge.ota import (
    DispatchBlocked,
    OTAConfig,
    build_ota_config_from_payload,
)
from swarmforge.topics import CONTROL_OTA_TOPIC, event_topic, node_ota_topic, telemetry_topic
from swarmforge.ota import select_canary_nodes


class RuntimeTransport(Protocol):
    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        ...

    def subscribe(self, topic: str, handler: Callable[[str, dict[str, Any]], None]) -> str:
        ...


@dataclass
class InMemoryBroker:
    """Small deterministic transport used for local replay and tests."""

    handlers: dict[str, dict[str, Callable[[str, dict[str, Any]], None]]] = field(
        default_factory=dict
    )
    next_sub_id: int = 1
    published_messages: list[dict[str, Any]] = field(default_factory=list)

    def subscribe(self, topic: str, handler: Callable[[str, dict[str, Any]], None]) -> str:
        token = f"sub-{self.next_sub_id}"
        self.next_sub_id += 1
        topic_handlers = self.handlers.setdefault(topic, {})
        topic_handlers[token] = handler
        return token

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        message = {"topic": topic, "payload": payload}
        self.published_messages.append(message)
        payload_copy = payload if isinstance(payload, dict) else {"_raw": payload}
        for handler in self.handlers.get(topic, {}).values():
            handler(topic, payload_copy)

    def unsubscribe(self, topic: str, token: str) -> None:
        handlers = self.handlers.get(topic, {})
        handlers.pop(token, None)


@dataclass
class EdgeNode:
    node_id: str
    broker: RuntimeTransport | None = None
    baseline_sampling_rate_hz: float = 10.0
    current_config: dict[str, Any] | None = None
    config_history: list[dict[str, Any]] = field(default_factory=list)
    event_history: list[dict[str, Any]] = field(default_factory=list)
    telemetry_history: list[dict[str, Any]] = field(default_factory=list)
    _subscription_token: str | None = None

    def attach_bus(self, broker: RuntimeTransport) -> "EdgeNode":
        self.broker = broker
        return self

    def connect(self) -> None:
        if self.broker is None:
            raise ValueError("broker must be attached before connect")
        self._subscription_token = self.broker.subscribe(
            node_ota_topic(self.node_id),
            self.on_ota_message,
        )

    def on_ota_message(self, topic: str, payload: dict[str, Any]) -> None:
        del topic
        self.current_config = self._coerce_ota_payload(payload, self.node_id)
        event = {
            "node_id": self.node_id,
            "event": "config_applied" if self.current_config else "config_rejected",
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if self.current_config is not None:
            event.update(
                {
                    "status": "accepted",
                    "config_version": self.current_config["config_version"],
                    "source_run_id": self.current_config["source_run_id"],
                }
            )
        else:
            event["status"] = "rejected"
            event["reason"] = _coerce_reason(payload)
        self.event_history.append(event)
        if self.broker is not None:
            self.broker.publish(event_topic(self.node_id), event)

    def _coerce_ota_payload(self, payload: Any, node_id: str) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            self.config_history.append({"node_id": node_id, "status": "rejected"})
            return None
        try:
            config = build_ota_config_from_payload(payload)
        except Exception as exc:
            self.config_history.append(
                {"node_id": node_id, "status": "rejected", "reason": str(exc)}
            )
            return None

        config_payload = config.to_dict()
        self.config_history.append({"node_id": node_id, "status": "applied", "config_version": config.config_version})
        return config_payload

    def publish_telemetry(self, telemetry_health: float) -> dict[str, Any]:
        if self.current_config is None:
            sampling_rate_hz = self.baseline_sampling_rate_hz
        else:
            sampling_rate_hz = float(self.current_config["sampling_rate_hz"])

        payload = {
            "node_id": self.node_id,
            "sampling_rate_hz": sampling_rate_hz,
            "telemetry_health": telemetry_health,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self.telemetry_history.append(payload)
        if self.broker is not None:
            self.broker.publish(telemetry_topic(self.node_id), payload)
        return payload

    def last_event(self) -> dict[str, Any] | None:
        if not self.event_history:
            return None
        return self.event_history[-1]


def dispatch_to_canary(
    broker: RuntimeTransport,
    config: OTAConfig,
    node_ids: list[str],
    percentage: float,
    run_id: str | None = None,
) -> dict[str, Any]:
    selected_nodes = tuple(select_canary_nodes(node_ids=node_ids, percentage=percentage))
    payload = config.to_dict()

    for node_id in selected_nodes:
        broker.publish(node_ota_topic(node_id), payload)

    if run_id is None:
        run_id = config.source_run_id

    broker.publish(
        CONTROL_OTA_TOPIC,
        {
            "run_id": run_id,
            "event": "canary_dispatch_completed",
            "target_nodes": list(selected_nodes),
        },
    )

    return {
        "run_id": run_id,
        "target_nodes": list(selected_nodes),
        "published": len(selected_nodes),
    }


def run_simple_canary(
    broker: RuntimeTransport,
    ready_payload: dict[str, Any],
    node_ids: list[str],
    *,
    plan_percentage: float | None = None,
) -> dict[str, Any]:
    config = _extract_ota_config(ready_payload)
    percentage = (
        float(plan_percentage)
        if plan_percentage is not None
        else float(ready_payload["plan"]["deployment"]["percentage"])
    )
    return dispatch_to_canary(
        broker=broker,
        config=config,
        node_ids=node_ids,
        percentage=percentage,
        run_id=ready_payload.get("run_id"),
    )


def _extract_ota_config(ready_payload: dict[str, Any]) -> OTAConfig:
    try:
        return build_ota_config_from_payload(ready_payload["ota"])
    except DispatchBlocked:
        raise
    except Exception as exc:
        raise DispatchBlocked(f"invalid ready payload: {exc}") from exc


def evaluate_canary_dispatch(
    dispatch_report: dict[str, Any],
    nodes: list[EdgeNode],
    *,
    telemetry_health_floor: float | None = None,
) -> dict[str, Any]:
    """Evaluate a dispatch report and canary runtime observations."""

    target_nodes = list(dispatch_report.get("target_nodes", []))
    node_map = {node.node_id: node for node in nodes}

    node_reports: list[dict[str, Any]] = []
    telemetry_samples: list[float] = []
    min_health = None
    all_applied = True

    for node_id in target_nodes:
        node = node_map.get(node_id)
        last_event = node.last_event() if node is not None else None

        if node is None:
            status = "missing"
            event = None
            all_applied = False
        elif last_event is None:
            status = "silent"
            event = None
            all_applied = False
        else:
            status = (
                "applied"
                if last_event.get("event") == "config_applied" and last_event.get("status") == "accepted"
                else "rejected"
            )
            if status != "applied":
                all_applied = False
            event = last_event

        health_values = [
            float(sample["telemetry_health"])
            for sample in (node.telemetry_history if node else [])
            if "telemetry_health" in sample
        ]
        if health_values:
            telemetry_samples.extend(health_values)
            min_health = min(health_values) if min_health is None else min(min_health, min(health_values))

        node_report = {
            "node_id": node_id,
            "status": status,
            "event": event,
            "telemetry_count": len(health_values),
            "telemetry_health_min": min(health_values) if health_values else None,
        }
        node_reports.append(node_report)

    health_violation = False
    if telemetry_health_floor is not None and telemetry_samples:
        health_violation = any(value < telemetry_health_floor for value in telemetry_samples)
    elif telemetry_health_floor is not None:
        # No telemetry means canary did not report status.
        all_applied = False

    return {
        "run_id": dispatch_report.get("run_id"),
        "target_nodes": target_nodes,
        "published": dispatch_report.get("published", 0),
        "telemetry_health_floor": telemetry_health_floor,
        "telemetry_samples_total": len(telemetry_samples),
        "telemetry_health_min": min_health,
        "all_nodes_applied": all_applied,
        "telemetry_violation": health_violation,
        "decision": "rollback" if (not all_applied or health_violation) else "promote",
        "node_reports": node_reports,
    }


def _coerce_reason(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("reason", "invalid_ota_payload"))
    return f"invalid_ota_payload:{type(payload).__name__}"
