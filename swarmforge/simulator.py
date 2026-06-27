from __future__ import annotations

import math
import random
from statistics import median

from swarmforge.schemas import (
    BaselineConfig,
    FilterSpec,
    OptimizationPlan,
    SimulationResult,
    TelemetryCollection,
)


PUBLISH_MODE_MULTIPLIERS = {
    "raw": 1.0,
    "summary": 0.45,
    "summary_and_anomalies": 0.55,
    "anomalies_only": 0.25,
}


def generate_accelerometer_signal(
    duration_seconds: int = 30,
    sample_rate_hz: float = 10,
    seed: int = 42,
) -> list[float]:
    rng = random.Random(seed)
    sample_count = int(duration_seconds * sample_rate_hz)
    values = []

    for index in range(sample_count):
        t = index / sample_rate_hz
        base_motion = math.sin(t * 1.2) * 0.8
        normal_noise = rng.uniform(-0.18, 0.18)
        terrain_noise = rng.uniform(-0.9, 0.9) if 10 <= t <= 20 else 0
        values.append(base_motion + normal_noise + terrain_noise)

    return values


def apply_filter(values: list[float], spec: FilterSpec) -> list[float]:
    if spec.type == "none":
        return list(values)
    if spec.type == "low_pass":
        return _low_pass(values, alpha=0.3)
    if spec.type == "moving_average":
        return _rolling_window(values, spec.window_size, average)
    if spec.type == "median":
        return _rolling_window(values, spec.window_size, median)
    raise ValueError(f"Unsupported filter type: {spec.type}")


def average(values: list[float]) -> float:
    return sum(values) / len(values)


def _rolling_window(values: list[float], window_size: int, reducer) -> list[float]:
    output = []
    half_window = window_size // 2

    for index in range(len(values)):
        start = max(0, index - half_window)
        end = min(len(values), index + half_window + 1)
        output.append(float(reducer(values[start:end])))

    return output


def _low_pass(values: list[float], alpha: float) -> list[float]:
    if not values:
        return []

    output = [values[0]]
    for value in values[1:]:
        output.append(alpha * value + (1 - alpha) * output[-1])

    return output


def resample(values: list[float], source_rate_hz: float, target_rate_hz: float) -> list[float]:
    if target_rate_hz >= source_rate_hz:
        return list(values)

    step = max(1, round(source_rate_hz / target_rate_hz))
    return values[::step]

def noise_score(values: list[float]) -> float:
    if len(values) < 2:
        return 0

    deltas = [abs(values[index] - values[index - 1]) for index in range(1, len(values))]
    return sum(deltas) / len(deltas)


def estimate_bandwidth_kbps(
    sampling_rate_hz: float,
    telemetry_collection: TelemetryCollection,
) -> float:
    base_overhead_bytes = 32
    bytes_per_metric = 16
    payload_per_sample_bytes = (
        base_overhead_bytes + bytes_per_metric * len(telemetry_collection.metrics)
    )
    publish_multiplier = PUBLISH_MODE_MULTIPLIERS[telemetry_collection.publish_mode]
    return sampling_rate_hz * payload_per_sample_bytes * 8 / 1000 * publish_multiplier


def latency_penalty_ms(
    filter_spec: FilterSpec,
    source_sample_rate_hz: float,
) -> float:
    if filter_spec.type == "none":
        return 0

    half_window = max(0, filter_spec.window_size - 1) / 2
    return half_window / source_sample_rate_hz * 1000


def simulate_plan(
    plan: OptimizationPlan,
    baseline: BaselineConfig | None = None,
    signal: list[float] | None = None,
) -> SimulationResult:
    baseline = baseline or BaselineConfig()
    signal = signal or generate_accelerometer_signal(
        sample_rate_hz=baseline.sampling_rate_hz,
    )

    baseline_values = apply_filter(signal, baseline.filter)
    candidate_values = apply_filter(signal, plan.filter)

    before_noise = noise_score(baseline_values)
    after_noise = noise_score(candidate_values)
    noise_reduction = _reduction_ratio(before_noise, after_noise)

    before_bandwidth = estimate_bandwidth_kbps(
        baseline.sampling_rate_hz,
        baseline.telemetry_collection,
    )
    after_bandwidth = estimate_bandwidth_kbps(
        plan.sampling_rate_hz,
        plan.telemetry_collection,
    )
    bandwidth_reduction = _reduction_ratio(before_bandwidth, after_bandwidth)
    latency_ms = latency_penalty_ms(plan.filter, baseline.sampling_rate_hz)

    score = score_candidate(
        intent=plan.intent,
        noise_reduction_ratio=noise_reduction,
        bandwidth_reduction_ratio=bandwidth_reduction,
        latency_penalty_ms=latency_ms,
        max_latency_ms=plan.rollback.max_latency_ms,
        estimated_payload_kbps=after_bandwidth,
        max_payload_kbps=plan.telemetry_collection.max_payload_kbps,
    )
    accepted, reason = decide(
        plan=plan,
        noise_score_before=before_noise,
        noise_score_after=after_noise,
        bandwidth_before_kbps=before_bandwidth,
        bandwidth_after_kbps=after_bandwidth,
        latency_ms=latency_ms,
        score=score,
    )

    return SimulationResult(
        accepted=accepted,
        reason=reason,
        noise_score_before=before_noise,
        noise_score_after=after_noise,
        noise_reduction_ratio=noise_reduction,
        bandwidth_before_kbps=before_bandwidth,
        bandwidth_after_kbps=after_bandwidth,
        bandwidth_reduction_ratio=bandwidth_reduction,
        latency_penalty_ms=latency_ms,
        payload_limit_kbps=plan.telemetry_collection.max_payload_kbps,
        estimated_payload_kbps=after_bandwidth,
        score=score,
    )


def score_candidate(
    intent: str,
    noise_reduction_ratio: float,
    bandwidth_reduction_ratio: float,
    latency_penalty_ms: float,
    max_latency_ms: float,
    estimated_payload_kbps: float,
    max_payload_kbps: float,
) -> float:
    latency_budget_remaining = 1 - min(latency_penalty_ms / max_latency_ms, 1)
    payload_budget_remaining = 1 - min(estimated_payload_kbps / max_payload_kbps, 1)
    weights = _score_weights(intent)

    score = (
        noise_reduction_ratio * weights["noise"]
        + bandwidth_reduction_ratio * weights["bandwidth"]
        + latency_budget_remaining * weights["latency"]
        + payload_budget_remaining * weights["payload"]
    )
    return max(0, min(score, 1))


def decide(
    plan: OptimizationPlan,
    noise_score_before: float,
    noise_score_after: float,
    bandwidth_before_kbps: float,
    bandwidth_after_kbps: float,
    latency_ms: float,
    score: float,
) -> tuple[bool, str]:
    if latency_ms > plan.rollback.max_latency_ms:
        return False, "Filter reduced noise but exceeded the latency budget."

    if bandwidth_after_kbps > plan.telemetry_collection.max_payload_kbps:
        return False, "Estimated telemetry payload exceeded the plan payload limit."

    if "noise" in plan.intent and noise_score_after >= noise_score_before:
        return False, "Noise score did not improve for a noise-focused request."

    if "bandwidth" in plan.intent and bandwidth_after_kbps >= bandwidth_before_kbps:
        return False, "Bandwidth did not improve for a bandwidth-focused request."

    if score < 0.6:
        return False, "Candidate score was below the acceptance threshold."

    if plan.intent == "reduce_bandwidth":
        return True, "Bandwidth improved within latency and payload limits."
    if plan.intent == "reduce_noise":
        return True, "Noise improved within latency and payload limits."
    return True, "Noise and bandwidth improved within latency and payload limits."


def _score_weights(intent: str) -> dict[str, float]:
    if intent == "reduce_bandwidth":
        return {
            "noise": 0.0,
            "bandwidth": 0.65,
            "latency": 0.25,
            "payload": 0.10,
        }
    if intent == "reduce_noise":
        return {
            "noise": 0.65,
            "bandwidth": 0.15,
            "latency": 0.15,
            "payload": 0.05,
        }
    return {
        "noise": 0.45,
        "bandwidth": 0.35,
        "latency": 0.15,
        "payload": 0.05,
    }


def _reduction_ratio(before: float, after: float) -> float:
    if before <= 0:
        return 0
    return max(0, (before - after) / before)
