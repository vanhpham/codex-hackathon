from __future__ import annotations

from swarmforge.risk import InvariantFailure
from swarmforge.scenarios import ScenarioSpec
from swarmforge.schemas import OptimizationPlan, SimulationResult


def check_invariants(
    plan: OptimizationPlan,
    scenario: ScenarioSpec,
    simulation: SimulationResult,
    telemetry_health: float,
) -> tuple[InvariantFailure, ...]:
    failures: list[InvariantFailure] = []

    if not plan.rollback.enabled:
        failures.append(
            InvariantFailure(
                name="rollback_enabled",
                reason="Rollback must remain enabled for every verified plan.",
                critical=True,
            )
        )

    if plan.deployment.strategy != "canary":
        failures.append(
            InvariantFailure(
                name="canary_required",
                reason="First deployment must use canary.",
                critical=True,
            )
        )

    if simulation.latency_penalty_ms > plan.rollback.max_latency_ms:
        failures.append(
            InvariantFailure(
                name="latency_within_budget",
                reason=(
                    f"Latency {simulation.latency_penalty_ms:.2f}ms exceeded "
                    f"budget {plan.rollback.max_latency_ms:.2f}ms."
                ),
                critical=True,
            )
        )

    if simulation.estimated_payload_kbps > plan.telemetry_collection.max_payload_kbps:
        failures.append(
            InvariantFailure(
                name="payload_within_cap",
                reason=(
                    f"Payload {simulation.estimated_payload_kbps:.4f}kbps exceeded "
                    f"cap {plan.telemetry_collection.max_payload_kbps:.4f}kbps."
                ),
                critical=True,
            )
        )

    if "noise" in plan.intent and simulation.noise_score_after >= simulation.noise_score_before:
        failures.append(
            InvariantFailure(
                name="noise_not_worse",
                reason=f"Noise did not improve in {scenario.scenario_id}.",
            )
        )

    if "bandwidth" in plan.intent and simulation.bandwidth_after_kbps >= simulation.bandwidth_before_kbps:
        failures.append(
            InvariantFailure(
                name="bandwidth_not_worse",
                reason=f"Bandwidth did not improve in {scenario.scenario_id}.",
            )
        )

    if telemetry_health < plan.rollback.min_telemetry_health:
        severe = telemetry_health < 0.8
        failures.append(
            InvariantFailure(
                name="telemetry_health_above_floor",
                reason=(
                    f"Telemetry health {telemetry_health:.4f} fell below "
                    f"floor {plan.rollback.min_telemetry_health:.4f}."
                ),
                critical=severe,
            )
        )

    return tuple(failures)
