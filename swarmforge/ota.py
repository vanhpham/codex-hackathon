from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


class DispatchBlocked(ValueError):
    """Raised when a result is not safe to dispatch."""


@dataclass(frozen=True)
class OTAConfig:
    config_version: str
    source_run_id: str
    sampling_rate_hz: float
    log_level: str
    filter: dict[str, Any]
    telemetry_collection: dict[str, Any]
    rollback: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_ota_config(harness_result: Any, config_version: str | None = None) -> OTAConfig:
    """Build OTA payload from harness or verification-style result."""

    result = _to_dict(harness_result)
    run_id, plan = _assert_deployment_ready(result)
    return build_ota_config_from_plan(plan, run_id=run_id, config_version=config_version)


def build_ota_config_from_payload(payload: Any) -> OTAConfig:
    """Build OTA payload from a previously generated OTA config payload."""

    data = _to_dict(payload)
    required = (
        "config_version",
        "source_run_id",
        "sampling_rate_hz",
        "log_level",
        "filter",
        "telemetry_collection",
        "rollback",
    )
    missing = [field for field in required if field not in data]
    if missing:
        raise DispatchBlocked(f"payload missing required keys: {', '.join(missing)}")

    try:
        return OTAConfig(
            config_version=str(data["config_version"]),
            source_run_id=str(data["source_run_id"]),
            sampling_rate_hz=float(data["sampling_rate_hz"]),
            log_level=str(data["log_level"]),
            filter=dict(data["filter"]),
            telemetry_collection=dict(data["telemetry_collection"]),
            rollback=dict(data["rollback"]),
        )
    except (TypeError, ValueError) as exc:
        raise DispatchBlocked(f"invalid OTA payload format: {exc}") from exc


def build_ota_config_from_plan(
    plan: Any,
    run_id: str | None = None,
    config_version: str | None = None,
) -> OTAConfig:
    plan_dict = _to_dict(plan)

    try:
        return OTAConfig(
            config_version=config_version or _default_config_version(run_id),
            source_run_id=str(run_id or "run_unknown"),
            sampling_rate_hz=float(plan_dict["sampling_rate_hz"]),
            log_level=str(plan_dict["log_level"]),
            filter=dict(plan_dict["filter"]),
            telemetry_collection=dict(plan_dict["telemetry_collection"]),
            rollback=dict(plan_dict["rollback"]),
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise DispatchBlocked(f"plan payload missing required fields: {exc}") from exc


def select_canary_nodes(node_ids: list[str], percentage: float) -> list[str]:
    if percentage <= 0 or percentage > 100:
        raise ValueError("percentage must be between 0 and 100")
    if not node_ids:
        return []

    sorted_nodes = sorted(node_ids)
    count = max(1, math.ceil(len(sorted_nodes) * percentage / 100))
    return sorted_nodes[:count]


def _assert_deployment_ready(result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    plan = result.get("plan")
    if not isinstance(plan, dict):
        raise DispatchBlocked("dispatch requires a result with a plan section")

    run_id = _extract_run_id(result)

    if _looks_like_harness_result(result):
        if result.get("status") != "ready_for_canary":
            raise DispatchBlocked("harness result must have status ready_for_canary")
        if result.get("plan_status") != "valid":
            raise DispatchBlocked("harness result must have plan_status valid")
        if result.get("simulation_status") != "accepted":
            raise DispatchBlocked("harness result must have simulation_status accepted")
        if result.get("deployment_decision") != "ready_for_canary":
            raise DispatchBlocked("harness result must have deployment_decision ready_for_canary")
        return run_id, plan

    verification = result.get("verification", result)
    if not isinstance(verification, dict):
        raise DispatchBlocked("verification section must be a mapping")

    decision = verification.get("decision") or verification.get("verification_status")
    if decision != "ready_for_canary":
        raise DispatchBlocked("verification decision must be ready_for_canary")

    risk_score = verification.get("risk_score")
    if risk_score is not None and float(risk_score) > 0.25:
        raise DispatchBlocked("risk score exceeds canary threshold")

    return run_id, plan


def _looks_like_harness_result(result: dict[str, Any]) -> bool:
    return "status" in result or "plan_status" in result or "deployment_decision" in result


def _extract_run_id(result: dict[str, Any]) -> str:
    if result.get("run_id"):
        return str(result["run_id"])
    if result.get("trace_id"):
        return str(result["trace_id"])
    if isinstance(result.get("verification"), dict) and result["verification"].get("run_id"):
        return str(result["verification"]["run_id"])
    return "run_unknown"


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError("harness_result must be a dict or expose to_dict()")


def _default_config_version(run_id: str | None) -> str:
    safe_run_id = "".join(
        char if char.isalnum() else "_"
        for char in str(run_id or "run_unknown")
    )
    return f"cfg_{safe_run_id}"
