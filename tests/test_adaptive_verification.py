from __future__ import annotations

import unittest

from swarmforge.adaptive_verification import generate_counterexample_candidates
from swarmforge.invariants import InvariantFailure
from swarmforge.risk import VerificationCaseResult
from swarmforge.schemas import FilterSpec, OptimizationPlan, RollbackPolicy, TelemetryCollection, DeploymentSpec


class _FakeLLMClient:
    def __init__(self, response):
        self.response = response

    def generate_counterexamples(self, prompt: str):
        return self.response


def _example_plan() -> OptimizationPlan:
    return OptimizationPlan(
        intent="reduce_noise_and_bandwidth",
        target_metric="accelerometer",
        sampling_rate_hz=2,
        log_level="WARNING",
        filter=FilterSpec(type="median", window_size=5),
        telemetry_collection=TelemetryCollection(
            metrics=("accelerometer", "temperature", "battery"),
            aggregation_window_seconds=5,
            publish_mode="summary_and_anomalies",
            max_payload_kbps=8,
        ),
        deployment=DeploymentSpec(
            strategy="canary",
            percentage=5,
            observation_window_seconds=10,
        ),
        rollback=RollbackPolicy(
            enabled=True,
            max_latency_ms=250,
            max_error_rate=0.02,
            min_telemetry_health=0.95,
        ),
    )


class AdaptiveVerificationTest(unittest.TestCase):
    def test_fallback_candidates_keep_seed_range_and_ids(self):
        failed_case = VerificationCaseResult(
            scenario_id="scenario_1",
            accepted=False,
            failed_invariants=(
                InvariantFailure(name="telemetry_health_above_floor", reason="telemetry too low"),
            ),
            metrics={"telemetry_health": 0.93},
            reason="telemetry too low",
        )

        candidates = generate_counterexample_candidates(
            plan=_example_plan(),
            failed_cases=(failed_case,),
            target_invariants=("telemetry_health_above_floor",),
            budget=3,
            seed_range=(101, 104),
        )

        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0].scenario_id.startswith("adaptive_"))
        self.assertEqual(candidates[0].seed, 101)

    def test_llm_payload_is_hard_filtered_to_budget_and_seed_range(self):
        failed_case = VerificationCaseResult(
            scenario_id="scenario_1",
            accepted=False,
            failed_invariants=(
                InvariantFailure(name="latency_within_budget", reason="latency too high"),
            ),
            metrics={"telemetry_health": 0.93},
            reason="latency too high",
        )

        client = _FakeLLMClient(
            {
                "reason": "stress",
                "scenarios": [
                    {
                        "terrain": "muddy",
                        "noise_level": "high",
                        "network_profile": "high_loss",
                        "battery_state": "critical",
                        "sensor_fault": "dropout",
                        "fleet_size": 50,
                        "seed": 901,
                    },
                ],
            }
        )

        cases = generate_counterexample_candidates(
            plan=_example_plan(),
            failed_cases=(failed_case,),
            target_invariants=("latency_within_budget",),
            budget=5,
            seed_range=(900, 902),
            client=client,
        )

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].seed, 901)
        self.assertEqual(cases[0].network_profile, "high_loss")
        self.assertEqual(cases[0].battery_state, "critical")

    def test_unsupported_llm_payload_falls_back_to_deterministic_generation(self):
        failed_case = VerificationCaseResult(
            scenario_id="scenario_1",
            accepted=False,
            failed_invariants=(InvariantFailure(name="telemetry_health_above_floor", reason="low"),),
            metrics={"telemetry_health": 0.85},
            reason="low",
        )

        class _BadClient:
            def generate_counterexamples(self, prompt: str) -> dict:
                return {"scenario": "invalid"}

        candidates = generate_counterexample_candidates(
            plan=_example_plan(),
            failed_cases=(failed_case,),
            target_invariants=("telemetry_health_above_floor",),
            budget=2,
            seed_range=(55, 57),
            client=_BadClient(),
        )

        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0].scenario_id.startswith("adaptive_"))
        self.assertEqual(candidates[0].seed, 55)

if __name__ == "__main__":
    unittest.main()
