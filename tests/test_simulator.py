from __future__ import annotations

import unittest

from swarmforge.schemas import OptimizationPlan
from swarmforge.simulator import simulate_plan


def plan(overrides=None):
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


class SimulatorTest(unittest.TestCase):
    def test_happy_path_is_accepted(self):
        result = simulate_plan(plan())

        self.assertTrue(result.accepted, result.to_dict())
        self.assertLess(result.noise_score_after, result.noise_score_before)
        self.assertLess(result.bandwidth_after_kbps, result.bandwidth_before_kbps)

    def test_oversized_filter_is_rejected_for_latency(self):
        candidate = plan({"filter.window_size": 15})
        result = simulate_plan(candidate)

        self.assertFalse(result.accepted)
        self.assertIn("latency", result.reason)

    def test_excess_payload_is_rejected(self):
        candidate = plan(
            {
                "sampling_rate_hz": 10,
                "filter.type": "none",
                "filter.window_size": 1,
                "telemetry_collection.metrics": [
                    "accelerometer",
                    "temperature",
                    "battery",
                    "bandwidth",
                    "telemetry_health",
                    "error_count",
                    "config_version",
                ],
                "telemetry_collection.publish_mode": "raw",
                "telemetry_collection.max_payload_kbps": 1,
            }
        )
        result = simulate_plan(candidate)

        self.assertFalse(result.accepted)
        self.assertIn("payload", result.reason)

    def test_no_useful_change_is_rejected(self):
        candidate = plan(
            {
                "sampling_rate_hz": 10,
                "filter.type": "none",
                "filter.window_size": 1,
                "telemetry_collection.metrics": [
                    "accelerometer",
                    "temperature",
                    "battery",
                    "bandwidth",
                ],
                "telemetry_collection.aggregation_window_seconds": 1,
                "telemetry_collection.publish_mode": "raw",
                "telemetry_collection.max_payload_kbps": 32,
            }
        )
        result = simulate_plan(candidate)

        self.assertFalse(result.accepted)
        self.assertIn("Noise score did not improve", result.reason)

    def test_bandwidth_only_plan_is_accepted(self):
        candidate = plan(
            {
                "intent": "reduce_bandwidth",
                "sampling_rate_hz": 2,
                "filter.type": "none",
                "filter.window_size": 1,
                "telemetry_collection.metrics": ["accelerometer", "temperature"],
                "telemetry_collection.publish_mode": "summary",
                "telemetry_collection.max_payload_kbps": 8,
            }
        )
        result = simulate_plan(candidate)

        self.assertTrue(result.accepted, result.to_dict())
        self.assertIn("Bandwidth improved", result.reason)


if __name__ == "__main__":
    unittest.main()
