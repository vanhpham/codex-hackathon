from __future__ import annotations

import json
import unittest

from swarmforge.schemas import DeploymentSpec, FilterSpec, OptimizationPlan, RollbackPolicy, TelemetryCollection
from swarmforge.verification import run_verification_matrix


def valid_plan(overrides=None) -> OptimizationPlan:
    data = {
        "intent": "reduce_noise_and_bandwidth",
        "target_metric": "accelerometer",
        "sampling_rate_hz": 2,
        "log_level": "WARNING",
        "filter": {
            "type": "median",
            "window_size": 5,
        },
        "telemetry_collection": {
            "metrics": ["accelerometer", "temperature", "battery"],
            "aggregation_window_seconds": 5,
            "publish_mode": "summary_and_anomalies",
            "max_payload_kbps": 8,
        },
        "deployment": {
            "strategy": "canary",
            "percentage": 5,
            "observation_window_seconds": 10,
        },
        "rollback": {
            "enabled": True,
            "max_latency_ms": 250,
            "max_error_rate": 0.02,
            "min_telemetry_health": 0.95,
        },
    }

    for path, value in (overrides or {}).items():
        target = data
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value

    return OptimizationPlan.from_dict(data)


class VerificationRunnerTest(unittest.TestCase):
    def test_good_plan_passes_verification_matrix(self):
        report = run_verification_matrix(valid_plan(), scenario_count=50)

        self.assertEqual(report.decision, "ready_for_canary", report.to_dict())
        self.assertGreaterEqual(report.pass_rate, 0.95)
        self.assertLessEqual(report.risk_score, 0.25)
        self.assertGreaterEqual(report.scenario_count, 50)

    def test_risky_filter_is_blocked(self):
        report = run_verification_matrix(
            valid_plan(
                {
                    "filter.window_size": 15,
                    "rollback.max_latency_ms": 100,
                }
            ),
            scenario_count=20,
        )

        self.assertEqual(report.decision, "blocked")
        self.assertIn("latency_within_budget", report.critical_failures)

    def test_high_loss_scenario_is_recorded(self):
        report = run_verification_matrix(valid_plan(), scenario_count=50)

        self.assertTrue(
            any("high_loss" in scenario_id for scenario_id in report.failed_scenarios),
            report.failed_scenarios,
        )

    def test_verification_replay_is_deterministic(self):
        first = run_verification_matrix(valid_plan(), scenario_count=25)
        second = run_verification_matrix(valid_plan(), scenario_count=25)

        self.assertEqual(first.to_dict(), second.to_dict())

    def test_critical_canary_invariant_blocks_regardless_of_pass_rate(self):
        plan = OptimizationPlan(
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
                strategy="full_after_canary",
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

        report = run_verification_matrix(plan, scenario_count=10)

        self.assertEqual(report.decision, "blocked")
        self.assertIn("canary_required", report.critical_failures)

    def test_risk_report_is_json_serializable(self):
        report = run_verification_matrix(valid_plan(), scenario_count=10)

        encoded = json.dumps(report.to_dict(), sort_keys=True)

        self.assertIn("case_results", encoded)


if __name__ == "__main__":
    unittest.main()
