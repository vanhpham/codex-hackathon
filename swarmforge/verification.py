from __future__ import annotations

import os
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

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
from swarmforge.adaptive_verification import generate_counterexample_candidates


DEFAULT_ADAPTIVE_WORKERS = max(1, min(4, (os.cpu_count() or 2) // 2))


@dataclass(frozen=True)
class VerificationPolicy:
    min_pass_rate: float = 0.95
    max_risk_score: float = 0.25


def run_verification_matrix(
    plan: OptimizationPlan,
    scenarios: list[ScenarioSpec] | None = None,
    scenario_count: int = 50,
    policy: VerificationPolicy | None = None,
    enable_adaptive: bool = False,
    workers: int = DEFAULT_ADAPTIVE_WORKERS,
    adaptive_budget: int = 20,
    adaptive_rounds: int = 1,
    seed_start: int = 1,
) -> RiskReport:
    policy = policy or VerificationPolicy()
    workers = max(1, workers)
    scenarios = scenarios or generate_scenario_matrix(count=scenario_count, seed_start=seed_start)
    scenario_list = list(scenarios)

    case_results = _run_case_batch(plan, scenario_list, workers)
    executed_scenarios = scenario_list
    adaptive_cycles = 0
    candidate_scenarios: tuple[str, ...] = ()
    adaptive_metadata: tuple[dict[str, Any], ...] = ()

    if enable_adaptive and adaptive_rounds > 0:
        all_failed = tuple(result for result in case_results if not result.accepted)

        for cycle in range(adaptive_rounds):
            if not all_failed:
                break

            target_invariants = _critical_failure_names(all_failed)
            base_seed = seed_start + len(scenario_list) + (cycle * adaptive_budget)
            seed_range = (base_seed, base_seed + adaptive_budget)
            candidates = generate_counterexample_candidates(
                plan=plan,
                failed_cases=all_failed,
                target_invariants=target_invariants,
                budget=adaptive_budget,
                seed_range=seed_range,
            )

            if not candidates:
                break

            # Avoid duplicate re-execution on fallback or repeated LLM output.
            seen = {result.scenario_id for result in case_results}
            filtered_candidates: list[ScenarioSpec] = []
            for candidate in candidates:
                if candidate.scenario_id in seen:
                    continue
                filtered_candidates.append(candidate)
                seen.add(candidate.scenario_id)
            candidates = tuple(filtered_candidates)
            if not candidates:
                break

            candidate_results = _run_case_batch(plan, candidates, workers)
            case_results += candidate_results
            executed_scenarios += candidates
            candidate_scenarios += tuple(result.scenario_id for result in candidate_results)
            adaptive_cycles += 1
            adaptive_metadata += (
                {
                    "cycle": cycle + 1,
                    "generated_candidates": len(candidates),
                    "seed_range": list(seed_range),
                    "target_invariants": list(target_invariants),
                    "failed_in_cycle": sum(1 for result in candidate_results if not result.accepted),
                    "passed_in_cycle": sum(1 for result in candidate_results if result.accepted),
                },
            )
            all_failed = tuple(result for result in candidate_results if not result.accepted)

    return build_risk_report(
        case_results,
        policy,
        executed_scenarios=tuple(spec.to_dict() for spec in executed_scenarios),
        adaptive_cycles=adaptive_cycles,
        candidate_scenarios=candidate_scenarios,
        adaptive_metadata=adaptive_metadata,
    )


def build_risk_report(
    case_results: tuple[VerificationCaseResult, ...],
    policy: VerificationPolicy | None = None,
    executed_scenarios: tuple[dict[str, Any], ...] | None = None,
    adaptive_cycles: int = 0,
    candidate_scenarios: tuple[str, ...] | None = None,
    adaptive_metadata: tuple[dict[str, Any], ...] | None = None,
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
        executed_scenarios=executed_scenarios or (),
        adaptive_cycles=adaptive_cycles,
        candidate_scenarios=candidate_scenarios or (),
        adaptive_metadata=adaptive_metadata or (),
    )


def _run_case_batch(
    plan: OptimizationPlan,
    scenarios: list[ScenarioSpec] | tuple[ScenarioSpec, ...],
    workers: int,
) -> tuple[VerificationCaseResult, ...]:
    scenario_list = list(scenarios)
    if workers <= 1 or len(scenario_list) <= 1:
        return tuple(_run_case(plan, scenario) for scenario in scenario_list)

    workers = min(workers, len(scenario_list))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_index: dict = {
            executor.submit(_run_case, plan, scenario): index
            for index, scenario in enumerate(scenario_list)
        }
        results: list[VerificationCaseResult | None] = [None] * len(scenario_list)

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            results[index] = future.result()

    # type: ignore[return-value]
    return tuple(result for result in results if result is not None)


def run_verification_case(plan: OptimizationPlan, scenario: ScenarioSpec) -> VerificationCaseResult:
    """Public helper for replaying a single case with the same deterministic logic."""

    return _run_case(plan, scenario)


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
