from __future__ import annotations

import unittest

from swarmforge.harness import run_harness


def valid_plan(overrides=None):
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
        "rationale": "Reduce noise and bandwidth with a bounded canary rollout.",
    }

    for path, value in (overrides or {}).items():
        target = data
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value

    return data


class FakePlanClient:
    def __init__(self, response):
        self.response = response

    def create_plan(self, prompt: str) -> dict:
        return self.response


class HarnessTest(unittest.TestCase):
    def test_valid_plan_reaches_ready_for_canary(self):
        result = run_harness("smooth the accelerometer", FakePlanClient(valid_plan()))

        self.assertEqual(result.status, "ready_for_canary")
        self.assertEqual(result.deployment_decision, "ready_for_canary")
        self.assertTrue(result.simulation_result["accepted"])

    def test_invalid_schema_is_blocked_before_simulation(self):
        result = run_harness(
            "deploy everywhere",
            FakePlanClient(valid_plan({"deployment.strategy": "full_fleet"})),
        )

        self.assertEqual(result.status, "schema_rejected")
        self.assertEqual(result.simulation_status, "not_started")
        self.assertIn("canary", result.validation_error)

    def test_simulator_rejection_blocks_deployment(self):
        result = run_harness(
            "use a very slow filter",
            FakePlanClient(valid_plan({"filter.window_size": 15})),
        )

        self.assertEqual(result.status, "simulation_rejected")
        self.assertEqual(result.deployment_decision, "blocked")
        self.assertIn("latency", result.simulation_result["reason"])


if __name__ == "__main__":
    unittest.main()
