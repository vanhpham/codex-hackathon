from __future__ import annotations

from typing import Any

from swarmforge.risk import RiskReport, SettingSuggestionReport
from swarmforge.schemas import OptimizationPlan


def suggest_setting_adjustments(
    plan: OptimizationPlan,
    report: RiskReport,
    max_suggestions: int = 3,
) -> SettingSuggestionReport:
    fail_blocks = set(report.critical_failures)
    safe_margin = 0.95 - report.pass_rate
    risk_gap = max(0.0, report.risk_score - 0.25)
    options: list[dict[str, Any]] = []
    options_by_group: dict[str, dict[str, Any]] = {}

    target_delta = 0.04 if report.decision == "blocked" else 0.02

    def add_option(
        group: str,
        changes: dict[str, Any],
        description: str,
        pass_rate_delta: float,
        risk_delta: float,
    ) -> None:
        option = {
            "description": description,
            "changes": changes,
            "risk_delta_preview": {
                "pass_rate_delta": round(pass_rate_delta, 4),
                "risk_score_delta": round(risk_delta, 4),
                "estimated_pass_rate": min(1.0, round(report.pass_rate + pass_rate_delta, 4)),
                "estimated_risk_score": max(0.0, round(report.risk_score + risk_delta, 4)),
            },
        }
        options_by_group.setdefault(group, option)

    def _safe_float(value: float, low: float, high: float) -> bool:
        return low <= value <= high

    def propose_sampling():
        if not _safe_float(plan.sampling_rate_hz - 1, 1.0, 20.0):
            return
        add_option(
            "sampling",
            {"sampling_rate_hz": max(1, int(plan.sampling_rate_hz - 1))},
            "Lower sample rate to reduce processing stress and bandwidth under bad links.",
            pass_rate_delta=target_delta,
            risk_delta=-0.06,
        )

    def propose_filter():
        if plan.filter.type == "median" and plan.filter.window_size < 9:
            next_window = plan.filter.window_size + 2
            if next_window % 2 == 0:
                next_window += 1
            if next_window <= 15:
                add_option(
                    "filter",
                    {"filter": {"type": "median", "window_size": next_window}},
                    "Increase median window gradually for bursty network and sensor faults.",
                    pass_rate_delta=0.02,
                    risk_delta=-0.03,
                )
        elif plan.filter.type == "none":
            add_option(
                "filter",
                {"filter": {"type": "moving_average", "window_size": 5}},
                "Introduce moving-average smoothing instead of no filtering.",
                pass_rate_delta=0.015,
                risk_delta=-0.02,
            )
        elif plan.filter.type == "moving_average" and plan.filter.window_size < 11:
            next_window = max(2, min(15, plan.filter.window_size + 2))
            add_option(
                "filter",
                {"filter": {"type": "moving_average", "window_size": next_window}},
                "Increase moving-average window for smoother derivative under noise.",
                pass_rate_delta=0.012,
                risk_delta=-0.025,
            )

    def propose_telemetry_cap():
        if "payload_within_cap" in fail_blocks or risk_gap > 0.08:
            proposed = max(1.0, plan.telemetry_collection.max_payload_kbps - 4.0)
            if proposed != plan.telemetry_collection.max_payload_kbps:
                add_option(
                    "telemetry_cap",
                    {"telemetry_collection": {"max_payload_kbps": round(proposed, 2)}},
                    "Tighten payload cap to reduce congestion and retry pressure.",
                    pass_rate_delta=0.008 if "payload_within_cap" in fail_blocks else 0.0,
                    risk_delta=-0.035,
                )

    def propose_canary_size():
        if "latency_within_budget" in fail_blocks and plan.deployment.percentage > 1:
            proposed = max(1, int(plan.deployment.percentage - 1))
            if proposed != plan.deployment.percentage:
                add_option(
                    "canary_percentage",
                    {"deployment": {"percentage": proposed}},
                    "Reduce canary blast radius to lower tail latency risk.",
                    pass_rate_delta=0.01,
                    risk_delta=-0.04,
                )

    propose_sampling()
    propose_filter()
    propose_telemetry_cap()
    propose_canary_size()

    options = [option for option in options_by_group.values() if _option_is_safe(plan, option)]

    if not options:
        return SettingSuggestionReport(
            reason="Plan is already at constrained-safe bounds; no immediate adjustment shown.",
            confidence=0.92,
            mutually_exclusive_options=(),
            risk_delta_preview={
                "pass_rate_delta": 0.0,
                "risk_score_delta": 0.0,
                "estimated_pass_rate": report.pass_rate,
                "estimated_risk_score": report.risk_score,
            },
        )

    options = sorted(
        options,
        key=lambda option: (option["risk_delta_preview"]["risk_score_delta"], -option["risk_delta_preview"]["pass_rate_delta"]),
    )[:max_suggestions]

    confidence = 0.45
    if report.decision == "blocked" and safe_margin > 0:
        confidence = 0.9
    elif safe_margin > 0 and "latency_within_budget" in fail_blocks:
        confidence = 0.83
    elif risk_gap > 0.05:
        confidence = 0.75

    reason = (
        f"Blocked run can improve by trying one option at a time, then re-running verification. "
        f"Current risk={report.risk_score:.2f}, pass_rate={report.pass_rate:.2f}."
    ) if report.decision == "blocked" else (
        "Safe alternatives for margin improvements are available."
    )

    return SettingSuggestionReport(
        reason=reason,
        confidence=round(confidence, 3),
        mutually_exclusive_options=tuple(options),
        risk_delta_preview={
            "pass_rate_delta": sum(opt["risk_delta_preview"]["pass_rate_delta"] for opt in options) / len(options),
            "risk_score_delta": sum(opt["risk_delta_preview"]["risk_score_delta"] for opt in options) / len(options),
            "estimated_pass_rate": min(1.0, report.pass_rate + safe_margin),
            "estimated_risk_score": max(0.0, report.risk_score - risk_gap / 2),
            "critical_failures": list(report.critical_failures),
        },
    )


def _option_is_safe(plan: OptimizationPlan, option: dict[str, Any]) -> bool:
    changes = option.get("changes", {})
    if "sampling_rate_hz" in changes:
        if not (1 <= changes["sampling_rate_hz"] <= 20):
            return False
    if "deployment" in changes:
        percentage = changes["deployment"].get("percentage")
        if percentage is None or not (1 <= percentage <= 20):
            return False
        if changes["deployment"].get("strategy") is not None:
            return False
    if "telemetry_collection" in changes:
        payload = changes["telemetry_collection"].get("max_payload_kbps")
        if payload is None or not (1 <= payload <= 64):
            return False
        # Keep same publish constraints; this suggestion only changes cap.
    if "filter" in changes:
        filter_type = changes["filter"].get("type")
        window_size = int(changes["filter"].get("window_size", 1))
        if filter_type not in {"none", "moving_average", "median", "low_pass"}:
            return False
        if not (1 <= window_size <= 15):
            return False
        if filter_type == "median" and window_size % 2 == 0:
            return False
        if filter_type in {"median", "moving_average"} and window_size < 1:
            return False
    return True
