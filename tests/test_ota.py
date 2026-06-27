from __future__ import annotations

import unittest

from swarmforge.harness import HarnessResult
from swarmforge.ota import DispatchBlocked, build_ota_config
from swarmforge.ota import build_ota_config_from_plan, select_canary_nodes
from swarmforge.topics import event_topic, node_ota_topic, telemetry_topic


def ready_result() -> HarnessResult:
    return HarnessResult(
        run_id="run_001",
        status="ready_for_canary",
        plan_status="valid",
        simulation_status="accepted",
        deployment_decision="ready_for_canary",
        plan={
            "sampling_rate_hz": 2,
            "log_level": "WARNING",
            "filter": {"type": "median", "window_size": 5},
            "telemetry_collection": {
                "metrics": ["accelerometer", "temperature", "battery"],
                "aggregation_window_seconds": 5,
                "publish_mode": "summary_and_anomalies",
                "max_payload_kbps": 8,
            },
            "rollback": {
                "enabled": True,
                "max_latency_ms": 250,
                "max_error_rate": 0.02,
                "min_telemetry_health": 0.95,
            },
        },
        simulation_result={"accepted": True},
    )


class OTATest(unittest.TestCase):
    def test_ready_result_builds_ota_config(self):
        config = build_ota_config(ready_result())

        self.assertEqual(config.config_version, "cfg_run_001")
        self.assertEqual(config.source_run_id, "run_001")
        self.assertEqual(config.sampling_rate_hz, 2)
        self.assertEqual(config.filter["type"], "median")

    def test_build_ota_config_from_plan(self):
        plan = {
            "sampling_rate_hz": 4,
            "log_level": "INFO",
            "filter": {"type": "moving_average", "window_size": 3},
            "telemetry_collection": {
                "metrics": ["accelerometer", "temperature", "battery"],
                "aggregation_window_seconds": 3,
                "publish_mode": "summary_and_anomalies",
                "max_payload_kbps": 12,
            },
            "rollback": {
                "enabled": True,
                "max_latency_ms": 350,
                "max_error_rate": 0.02,
                "min_telemetry_health": 0.95,
            },
        }

        config = build_ota_config_from_plan(plan, run_id="run_999")
        self.assertEqual(config.source_run_id, "run_999")
        self.assertEqual(config.filter["type"], "moving_average")
        self.assertEqual(config.sampling_rate_hz, 4)

    def test_rejected_result_cannot_build_ota_config(self):
        result = ready_result()
        blocked_result = HarnessResult(
            **{
                **result.to_dict(),
                "status": "simulation_rejected",
                "simulation_status": "rejected",
                "deployment_decision": "blocked",
            }
        )

        with self.assertRaises(DispatchBlocked):
            build_ota_config(blocked_result)

    def test_verification_report_ready_payload_can_build_ota_config(self):
        verification_ready = {
            "run_id": "run_trace_001",
            "plan": {
                "sampling_rate_hz": 3,
                "log_level": "WARNING",
                "filter": {"type": "median", "window_size": 7},
                "telemetry_collection": {
                    "metrics": ["accelerometer", "temperature", "battery"],
                    "aggregation_window_seconds": 5,
                    "publish_mode": "summary_and_anomalies",
                    "max_payload_kbps": 8,
                },
                "rollback": {
                    "enabled": True,
                    "max_latency_ms": 250,
                    "max_error_rate": 0.02,
                    "min_telemetry_health": 0.95,
                },
            },
            "verification": {
                "decision": "ready_for_canary",
                "risk_score": 0.12,
            },
        }

        config = build_ota_config(verification_ready)
        self.assertEqual(config.source_run_id, "run_trace_001")
        self.assertEqual(config.filter["window_size"], 7)

    def test_verification_report_blocked_payload_is_rejected(self):
        verification_blocked = {
            "run_id": "run_trace_002",
            "plan": {
                "sampling_rate_hz": 3,
                "log_level": "WARNING",
                "filter": {"type": "median", "window_size": 7},
                "telemetry_collection": {
                    "metrics": ["accelerometer", "temperature", "battery"],
                    "aggregation_window_seconds": 5,
                    "publish_mode": "summary_and_anomalies",
                    "max_payload_kbps": 8,
                },
                "rollback": {
                    "enabled": True,
                    "max_latency_ms": 250,
                    "max_error_rate": 0.02,
                    "min_telemetry_health": 0.95,
                },
            },
            "verification": {
                "decision": "blocked",
                "risk_score": 0.5,
            },
        }

        with self.assertRaises(DispatchBlocked):
            build_ota_config(verification_blocked)

    def test_canary_selection_is_deterministic(self):
        nodes = [f"node-{index:02d}" for index in range(10, 0, -1)]

        self.assertEqual(select_canary_nodes(nodes, 5), ["node-01"])
        self.assertEqual(select_canary_nodes(nodes, 20), ["node-01", "node-02"])

    def test_topic_mapping(self):
        self.assertEqual(node_ota_topic("node-01"), "swarm/node/node-01/ota")
        self.assertEqual(telemetry_topic("node-01"), "swarm/telemetry/node-01")
        self.assertEqual(event_topic("node-01"), "swarm/events/node-01")

    def test_topic_rejects_wildcards(self):
        with self.assertRaises(ValueError):
            node_ota_topic("node/+")


if __name__ == "__main__":
    unittest.main()
