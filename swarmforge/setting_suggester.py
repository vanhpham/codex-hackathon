from __future__ import annotations

import os
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from swarmforge.risk import RiskReport, SettingSuggestionReport
from swarmforge.schemas import OptimizationPlan


class _LLMError(RuntimeError):
    pass


class SettingSuggestionClient(Protocol):
    def generate_setting_suggestions(self, prompt: str) -> dict[str, Any]:
        ...


class LLMSettingOptionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=8, max_length=180)
    rationale: str = Field(min_length=1, max_length=280)
    changes: dict[str, Any] = Field(min_length=1)
    expected_pass_rate_delta: float = Field(ge=-0.20, le=0.40)
    expected_risk_score_delta: float = Field(ge=-0.60, le=0.40)


class LLMSettingSuggestionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)
    options: list[LLMSettingOptionOutput] = Field(default_factory=list)


class OpenAISettingSuggestionClient:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        from openai import OpenAI

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate_setting_suggestions(self, prompt: str) -> dict[str, Any]:
        response = self.client.responses.parse(
            model=self.model,
            input=prompt,
            text_format=LLMSettingSuggestionOutput,
            max_output_tokens=1200,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise _LLMError("OpenAI response did not include parsed setting suggestions")
        return parsed.model_dump()


def suggest_setting_adjustments(
    plan: OptimizationPlan,
    report: RiskReport,
    max_suggestions: int = 3,
    *,
    client: SettingSuggestionClient | None = None,
    use_llm: bool = False,
) -> SettingSuggestionReport:
    rule_based_options = _generate_rule_based_options(plan=plan, report=report)
    rule_based_options = [dict(option, source="heuristic") for option in rule_based_options]

    ai_options = []
    llm_confidence = None
    if use_llm and client is not None:
        try:
            prompt = _build_ai_prompt(plan, report, max_suggestions=max_suggestions)
            payload = client.generate_setting_suggestions(prompt)
            parsed = LLMSettingSuggestionOutput.model_validate(payload)
            llm_confidence = parsed.confidence
            ai_options = _normalize_ai_options(
                plan=plan,
                report=report,
                options=parsed.options,
                max_suggestions=max_suggestions,
            )
        except Exception:
            # Keep strict fallback: if the LLM path fails at any point, still keep deterministic options.
            ai_options = []

    options = [option for option in (*rule_based_options, *ai_options) if _option_is_safe(plan, option)]
    options = _dedupe_options(options)

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

    safe_margin = 0.95 - report.pass_rate
    risk_gap = max(0.0, report.risk_score - 0.25)
    base_confidence = 0.45
    if report.decision == "blocked" and safe_margin > 0:
        base_confidence = 0.9
    elif safe_margin > 0 and "latency_within_budget" in set(report.critical_failures):
        base_confidence = 0.83
    elif risk_gap > 0.05:
        base_confidence = 0.75
    if llm_confidence is not None:
        base_confidence = round((base_confidence + (0.65 * llm_confidence)) / 1.65, 3)

    options = sorted(
        options,
        key=lambda option: (
            option["risk_delta_preview"]["risk_score_delta"],
            -option["risk_delta_preview"]["pass_rate_delta"],
        ),
    )[:max_suggestions]

    confidence = round(max(base_confidence, 0.1), 3)
    if llm_confidence is not None:
        confidence = round((confidence + llm_confidence) / 2, 3)

    reason = (
        f"Blocked run can improve by trying one option at a time, then re-running verification. "
        f"Current risk={report.risk_score:.2f}, pass_rate={report.pass_rate:.2f}."
    ) if report.decision == "blocked" else (
        "Safe alternatives for margin improvements are available."
    )
    if llm_confidence is not None:
        reason = (
            f"{reason} LLM-assisted tuning suggestions included with advisory confidence {llm_confidence:.2f}."
        )

    return SettingSuggestionReport(
        reason=reason,
        confidence=confidence,
        mutually_exclusive_options=tuple(options),
        risk_delta_preview={
            "pass_rate_delta": sum(option["risk_delta_preview"]["pass_rate_delta"] for option in options) / len(options),
            "risk_score_delta": sum(option["risk_delta_preview"]["risk_score_delta"] for option in options) / len(options),
            "estimated_pass_rate": min(1.0, report.pass_rate + safe_margin),
            "estimated_risk_score": max(0.0, report.risk_score - risk_gap / 2),
            "critical_failures": list(report.critical_failures),
            "includes_ai": llm_confidence is not None,
        },
    )


def _build_ai_prompt(plan: OptimizationPlan, report: RiskReport, max_suggestions: int) -> str:
    failed = ", ".join(report.critical_failures) if report.critical_failures else "none"
    return f"""
You are the post-verification tuning advisor for edge-telemetry control.
Use only safe deltas that preserve canary-first rollout and rollback enabled.

Current context:
- decision={report.decision}
- pass_rate={report.pass_rate:.4f}
- risk_score={report.risk_score:.4f}
- critical_failures={failed}

Current plan:
- intent={plan.intent}
- target_metric={plan.target_metric}
- sampling_rate_hz={plan.sampling_rate_hz}
- filter={plan.filter.type}:{plan.filter.window_size}
- telemetry_cap={plan.telemetry_collection.max_payload_kbps}
- aggregation_window={plan.telemetry_collection.aggregation_window_seconds}
- canary_percentage={plan.deployment.percentage}
- rollback_latency_budget={plan.rollback.max_latency_ms}
- min_telemetry_health={plan.rollback.min_telemetry_health}

Return up to {max_suggestions} suggestions that can improve throughput under failure patterns.
Focus on safe changes to:
- sampling_rate_hz
- telemetry_collection.max_payload_kbps
- telemetry_collection.aggregation_window_seconds
- filter settings
- deployment.percentage

Do NOT change strategy, disable rollback, or publish mode.
""".strip()


def _generate_rule_based_options(plan: OptimizationPlan, report: RiskReport) -> list[dict[str, Any]]:
    fail_blocks = set(report.critical_failures)
    options: list[dict[str, Any]] = []
    options_by_group: dict[str, dict[str, Any]] = {}
    target_delta = 0.04 if report.decision == "blocked" else 0.02
    safe_margin = 0.95 - report.pass_rate
    risk_gap = max(0.0, report.risk_score - 0.25)

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
            "source": "heuristic",
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
        if _safe_float(plan.sampling_rate_hz - 1, 1.0, 20.0):
            add_option(
                "sampling",
                {"sampling_rate_hz": max(1, int(plan.sampling_rate_hz - 1))},
                "Lower sample rate to reduce processing and telemetry volume.",
                pass_rate_delta=max(0.0, target_delta - (safe_margin * 0.05)),
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

    def propose_aggregation_window():
        if report.decision != "blocked" and not risk_gap:
            return
        window = plan.telemetry_collection.aggregation_window_seconds + 1
        if window <= 60:
            add_option(
                "aggregation_window",
                {"telemetry_collection": {"aggregation_window_seconds": int(window)}},
                "Increase aggregation window to lower publish frequency under load.",
                pass_rate_delta=0.005,
                risk_delta=-0.015,
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
    propose_aggregation_window()
    propose_canary_size()

    return [option for option in options_by_group.values()]


def _normalize_ai_options(
    plan: OptimizationPlan,
    report: RiskReport,
    options: list[LLMSettingOptionOutput],
    *,
    max_suggestions: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for option in options[:max_suggestions]:
        candidate_changes = _sanitize_changes(option.changes)
        if not candidate_changes:
            continue
        mapped = {
            "description": option.description,
            "changes": candidate_changes,
            "source": "llm",
            "risk_delta_preview": {
                "pass_rate_delta": round(option.expected_pass_rate_delta, 4),
                "risk_score_delta": round(option.expected_risk_score_delta, 4),
                "estimated_pass_rate": min(1.0, max(0.0, report.pass_rate + option.expected_pass_rate_delta)),
                "estimated_risk_score": max(0.0, report.risk_score + option.expected_risk_score_delta),
            },
        }
        if _option_is_safe(plan, mapped):
            out.append(mapped)
    return out


def _sanitize_changes(raw_changes: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw_changes, dict):
        return None

    allowed = {"sampling_rate_hz", "filter", "telemetry_collection", "deployment"}
    unknown = set(raw_changes) - allowed
    if unknown:
        return None

    out: dict[str, Any] = {}
    for key, value in raw_changes.items():
        if key == "sampling_rate_hz":
            normalized = _coerce_float(value)
            if normalized is None:
                return None
            out[key] = normalized
            continue

        if key == "deployment":
            if not isinstance(value, dict):
                return None
            percentage = value.get("percentage")
            if percentage is None:
                return None
            normalized = _coerce_int(percentage)
            if normalized is None:
                return None
            out[key] = {"percentage": normalized}
            continue

        if key == "telemetry_collection":
            if not isinstance(value, dict):
                return None
            normalized_collection: dict[str, Any] = {}
            if "max_payload_kbps" in value:
                payload = _coerce_float(value.get("max_payload_kbps"))
                if payload is None:
                    return None
                normalized_collection["max_payload_kbps"] = payload
            if "aggregation_window_seconds" in value:
                agg = _coerce_int(value.get("aggregation_window_seconds"))
                if agg is None:
                    return None
                normalized_collection["aggregation_window_seconds"] = agg
            if not normalized_collection:
                return None
            out[key] = normalized_collection
            continue

        if key == "filter":
            if not isinstance(value, dict):
                return None
            filter_type = value.get("type")
            if filter_type is None:
                return None
            window = _coerce_int(value.get("window_size", 1))
            if window is None:
                return None
            out[key] = {
                "type": str(filter_type),
                "window_size": window,
            }
            continue

        return None

    return out


def _coerce_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _coerce_int(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _dedupe_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped: list[dict[str, Any]] = []
    for option in options:
        marker = (
            option.get("description", ""),
            str(option.get("changes", {})),
        )
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(option)
    return deduped


def _option_is_safe(plan: OptimizationPlan, option: dict[str, Any]) -> bool:
    del plan
    changes = option.get("changes", {})
    if not isinstance(changes, dict):
        return False

    allowed_keys = {"sampling_rate_hz", "filter", "telemetry_collection", "deployment"}
    if set(changes) - allowed_keys:
        return False

    if "sampling_rate_hz" in changes:
        if not (1 <= changes["sampling_rate_hz"] <= 20):
            return False
    if "deployment" in changes:
        deployment_changes = changes["deployment"]
        if not isinstance(deployment_changes, dict):
            return False
        percentage = deployment_changes.get("percentage")
        if percentage is None or not (1 <= int(percentage) <= 20):
            return False
        if deployment_changes.get("strategy") is not None:
            return False
    if "telemetry_collection" in changes:
        telemetry_collection_changes = changes["telemetry_collection"]
        if not isinstance(telemetry_collection_changes, dict):
            return False
        if "max_payload_kbps" in telemetry_collection_changes:
            payload = telemetry_collection_changes["max_payload_kbps"]
            if payload is None or not (1 <= float(payload) <= 64):
                return False
        if "aggregation_window_seconds" in telemetry_collection_changes:
            aggregation = telemetry_collection_changes["aggregation_window_seconds"]
            if aggregation is None or not (1 <= int(aggregation) <= 60):
                return False
        # Keep same publish constraints; this suggestion only changes bandwidth controls.
    if "filter" in changes:
        filter_changes = changes["filter"]
        if not isinstance(filter_changes, dict):
            return False
        filter_type = str(filter_changes.get("type"))
        window_size = int(filter_changes.get("window_size", 1))
        if filter_type not in {"none", "moving_average", "median", "low_pass"}:
            return False
        if not (1 <= window_size <= 15):
            return False
        if filter_type == "median" and window_size % 2 == 0:
            return False
        if filter_type in {"median", "moving_average"} and window_size < 1:
            return False
    return True
