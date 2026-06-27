from __future__ import annotations

from dataclasses import dataclass

from swarmforge.invariants import check_invariants
from swarmforge.risk import InvariantFailure, RiskReport, VerificationCaseResult
from swarmforge.scenarios import (
    ScenarioSpec,
    estimate_telemetry_health,
    generate_scenario_matrix,
    scenario_signal,
)
from swarmforge.schemas import OptimizationPlan
from swarmforge.simulator import simulate_plan


@dataclass(frozen=True)
class VerificationPolicy:
    min_pass_rate: float = 0.95
    max_risk_score: float = 0.25


def run_verification_matrix(
    plan: OptimizationPlan,
    scenarios: list[ScenarioSpec] | None = None,
    scenario_count: int = 50,
    policy: VerificationPolicy | None = None,
) -> RiskReport:
    policy = policy or VerificationPolicy()
    scenarios = scenarios or generate_scenario_matrix(count=scenario_count)
    case_results = tuple(_run_case(plan, scenario) for scenario in scenarios)
    return build_risk_report(case_results, policy)


def build_risk_report(
    case_results: tuple[VerificationCaseResult, ...],
    policy: VerificationPolicy | None = None,
) -> RiskReport:
    if not case_results:
        raise ValueError("case_results must not be empty")

    policy = policy or VerificationPolicy()
    scenario_count = len(case_results)
    passed_count = sum(1 for result in case_results if result.accepted)
    failed_count = scenario_count - passed_count
    pass_rate = passed_count / scenario_count
    critical_failures = _critical_failure_names(case_results)
    risk_score = _risk_score(case_results)
    failed_scenarios = tuple(result.scenario_id for result in case_results if not result.accepted)
    worst_case = _worst_case(case_results)

    passed = (
        pass_rate >= policy.min_pass_rate
        and risk_score <= policy.max_risk_score
        and not critical_failures
    )

    return RiskReport(
        verification_status="passed" if passed else "failed",
        scenario_count=scenario_count,
        passed_count=passed_count,
        failed_count=failed_count,
        pass_rate=pass_rate,
        risk_score=risk_score,
        worst_case=worst_case,
        failed_scenarios=failed_scenarios,
        critical_failures=critical_failures,
        decision="ready_for_canary" if passed else "blocked",
        case_results=case_results,
    )


def _run_case(plan: OptimizationPlan, scenario: ScenarioSpec) -> VerificationCaseResult:
    signal = scenario_signal(scenario)
    simulation = simulate_plan(plan, signal=signal)
    telemetry_health = estimate_telemetry_health(scenario)
    failures = check_invariants(
        plan=plan,
        scenario=scenario,
        simulation=simulation,
        telemetry_health=telemetry_health,
    )
    accepted = not failures
    metrics = {
        **simulation.to_dict(),
        "telemetry_health": telemetry_health,
        "fleet_size": float(scenario.fleet_size),
    }

    return VerificationCaseResult(
        scenario_id=scenario.scenario_id,
        accepted=accepted,
        failed_invariants=failures,
        metrics=metrics,
        reason=_case_reason(failures),
    )


def _case_reason(failures: tuple[InvariantFailure, ...]) -> str:
    if not failures:
        return "Safety invariants passed."
    return "; ".join(failure.reason for failure in failures)


def _critical_failure_names(case_results: tuple[VerificationCaseResult, ...]) -> tuple[str, ...]:
    names = {
        failure.name
        for result in case_results
        for failure in result.failed_invariants
        if failure.critical
    }
    return tuple(sorted(names))


def _risk_score(case_results: tuple[VerificationCaseResult, ...]) -> float:
    failure_ratio = sum(1 for result in case_results if not result.accepted) / len(case_results)
    critical_penalty = 0.35 if _critical_failure_names(case_results) else 0
    health_penalty = max(
        0.0,
        1 - min(result.metrics.get("telemetry_health", 1.0) for result in case_results),
    )
    return min(1.0, failure_ratio * 0.7 + critical_penalty + health_penalty * 0.2)


def _worst_case(case_results: tuple[VerificationCaseResult, ...]) -> dict:
    worst = min(case_results, key=lambda result: result.metrics.get("telemetry_health", 1.0))
    return {
        "scenario_id": worst.scenario_id,
        "telemetry_health": worst.metrics.get("telemetry_health"),
        "score": worst.metrics.get("score"),
        "accepted": worst.accepted,
    }
