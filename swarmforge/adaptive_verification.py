from __future__ import annotations

import os
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from swarmforge.scenarios import ScenarioSpec
from swarmforge.schemas import OptimizationPlan


class _LLMError(RuntimeError):
    pass


class CounterexampleFuzzerClient(Protocol):
    def generate_counterexamples(self, prompt: str) -> dict[str, Any]:
        ...


class CounterexampleScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terrain: Literal["smooth", "muddy", "rocky", "spike_noise"]
    noise_level: Literal["low", "medium", "high"]
    network_profile: Literal["stable", "jitter", "high_loss"]
    battery_state: Literal["normal", "low", "critical"]
    sensor_fault: Literal["none", "dropout", "stuck_value"]
    fleet_size: int = Field(ge=1, le=1000)
    duration_seconds: int = Field(default=30, ge=10, le=120)
    baseline_sample_rate_hz: float = Field(default=10.0, ge=1, le=20)
    seed: int = Field(default=1, ge=1, le=10_000_000)


class CounterexampleBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)
    scenarios: list[CounterexampleScenario]


class OpenAIAdaptiveScenarioClient:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        from openai import OpenAI

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate_counterexamples(self, prompt: str) -> dict[str, Any]:
        response = self.client.responses.parse(
            model=self.model,
            input=prompt,
            text_format=CounterexampleBatch,
            max_output_tokens=1200,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise _LLMError("OpenAI response did not include parsed counterexamples")
        return parsed.model_dump()


def generate_counterexample_candidates(
    plan: OptimizationPlan,
    failed_cases: tuple[Any, ...],
    target_invariants: tuple[str, ...],
    budget: int,
    seed_range: tuple[int, int],
    *,
    client: CounterexampleFuzzerClient | None = None,
) -> tuple[ScenarioSpec, ...]:
    if budget <= 0:
        return ()

    if not failed_cases:
        return ()

    start, end = seed_range
    if start >= end:
        raise ValueError("seed_range end must be greater than start")

    bounded_budget = min(budget, max(0, end - start))
    if bounded_budget <= 0:
        return ()

    if client is not None:
        try:
            prompt = _build_prompt(plan, failed_cases, target_invariants)
            payload = client.generate_counterexamples(prompt)
            if not payload.get("scenarios"):
                raise _LLMError("empty scenario payload")
            return _parse_llm_payload(payload, bounded_budget, seed_range)
        except Exception:
            # Fail-safe fallback keeps verification pipeline running without external dependency.
            pass

    return tuple(_fallback_candidate_generator(plan, failed_cases, target_invariants, bounded_budget, seed_range))


def _build_prompt(plan: OptimizationPlan, failed_cases, target_invariants: tuple[str, ...]) -> str:
    failed_ids = ", ".join(
        f"{case.scenario_id}:{','.join(f.name for f in case.failed_invariants) or 'none'}"
        for case in failed_cases[:5]
    )
    return f"""
Generate up to bounded adversarial scenarios for deeper verification.

Context:
intent={plan.intent}
target={plan.target_metric}
sampling_rate_hz={plan.sampling_rate_hz}
filter={plan.filter.type}:{plan.filter.window_size}
telemetry_cap={plan.telemetry_collection.max_payload_kbps}
failed_invariants={','.join(target_invariants)}
recent_failures={failed_ids}

Return only scenario specs from the fixed enum domains.
"""


def _parse_llm_payload(
    payload: dict[str, Any],
    budget: int,
    seed_range: tuple[int, int],
) -> tuple[ScenarioSpec, ...]:
    raw = payload.get("scenarios", []) or []
    parsed = CounterexampleBatch(
        reason=payload.get("reason", "auto-generated"),
        scenarios=raw,
    ).model_dump()
    start, end = seed_range
    seed_cursor = start
    out: list[ScenarioSpec] = []

    for spec in parsed["scenarios"][:budget]:
        requested_seed = int(spec.get("seed", seed_cursor))
        if requested_seed < start or requested_seed >= end:
            requested_seed = seed_cursor
        seed_cursor += 1

        scenario = _coerce_spec(
            spec,
            requested_seed,
        )
        out.append(scenario)

    return tuple(out)


def _coerce_spec(spec: dict[str, Any], seed: int) -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id=f"llm_{spec['terrain']}_{spec['noise_level']}_{spec['network_profile']}_"
        f"{spec['battery_state']}_{spec['sensor_fault']}_seed_{seed}",
        seed=seed,
        duration_seconds=_clamp_int(spec.get("duration_seconds", 30), 10, 120),
        baseline_sample_rate_hz=_clamp_float(spec.get("baseline_sample_rate_hz", 10.0), 1.0, 20.0),
        terrain=spec["terrain"],
        noise_level=spec["noise_level"],
        network_profile=spec["network_profile"],
        battery_state=spec["battery_state"],
        sensor_fault=spec["sensor_fault"],
        fleet_size=_clamp_int(spec.get("fleet_size", 50), 1, 1000),
    )


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(round(float(value)))))


def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _fallback_candidate_generator(
    plan: OptimizationPlan,
    failed_cases: tuple[Any, ...],
    target_invariants: tuple[str, ...],
    budget: int,
    seed_range: tuple[int, int],
) -> tuple[ScenarioSpec, ...]:
    out: list[ScenarioSpec] = []
    start, end = seed_range

    for index, failed in enumerate(failed_cases[:budget]):
        seed = start + index
        if seed >= end:
            break

        failed_invariants = {failure.name for failure in failed.failed_invariants}
        focus = target_invariants or tuple(sorted(failed_invariants))

        terrain: Literal["smooth", "muddy", "rocky", "spike_noise"] = "muddy"
        noise_level: Literal["low", "medium", "high"] = "medium"
        network_profile: Literal["stable", "jitter", "high_loss"] = "stable"
        battery_state: Literal["normal", "low", "critical"] = "normal"
        fault: Literal["none", "dropout", "stuck_value"] = "none"

        if "latency_within_budget" in focus:
            network_profile = "high_loss"
            battery_state = "critical"
        elif "payload_within_cap" in focus:
            network_profile = "jitter"
            terrain = "rocky"
            fault = "stuck_value"
        elif "telemetry_health_above_floor" in focus:
            network_profile = "high_loss"
            terrain = "spike_noise"
            fault = "none"
            battery_state = "critical"

        if "noise_not_worse" in focus:
            noise_level = "high"
            terrain = "spike_noise" if terrain == "muddy" else terrain

        if "bandwidth_not_worse" in focus:
            fault = "stuck_value"
        elif fault != "stuck_value":
            fault = "dropout" if index % 2 == 0 else "none"

        if "fleet_size" in focus:
            fleet = 100
        else:
            fleet = 50

        out.append(
            ScenarioSpec(
                scenario_id=_scenario_id_from_focus(terrain, noise_level, network_profile, battery_state, fault, seed),
                seed=seed,
                duration_seconds=30,
                baseline_sample_rate_hz=max(1.0, min(10.0, plan.sampling_rate_hz - 0.5)),
                terrain=terrain,
                noise_level=noise_level,
                network_profile=network_profile,
                battery_state=battery_state,
                sensor_fault=fault,
                fleet_size=fleet,
            )
        )

    return tuple(out)


def _scenario_id_from_focus(
    terrain: str,
    noise_level: str,
    network_profile: str,
    battery_state: str,
    sensor_fault: str,
    seed: int,
) -> str:
    return f"adaptive_{terrain}_{noise_level}_{network_profile}_{battery_state}_{sensor_fault}_seed_{seed}"
