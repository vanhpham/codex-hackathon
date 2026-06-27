from __future__ import annotations


CONTROL_OTA_TOPIC = "swarm/control/ota"


def node_ota_topic(node_id: str) -> str:
    return f"swarm/node/{_clean_node_id(node_id)}/ota"


def telemetry_topic(node_id: str) -> str:
    return f"swarm/telemetry/{_clean_node_id(node_id)}"


def event_topic(node_id: str) -> str:
    return f"swarm/events/{_clean_node_id(node_id)}"


def _clean_node_id(node_id: str) -> str:
    normalized = node_id.strip()
    if not normalized or "/" in normalized or "#" in normalized or "+" in normalized:
        raise ValueError("node_id must be non-empty and must not include MQTT wildcards")
    return normalized

