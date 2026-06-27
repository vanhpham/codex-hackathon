from __future__ import annotations

import unittest

from swarmforge.edge_runtime import (
    InMemoryBroker,
    EdgeNode,
    dispatch_to_canary,
    evaluate_canary_dispatch,
)
from swarmforge.ota import build_ota_config_from_plan


def _sample_ota_plan():
    return {
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
    }


class EdgeRuntimeTest(unittest.TestCase):
    def test_edge_node_accepts_valid_ota_payload(self):
        broker = InMemoryBroker()
        config = build_ota_config_from_plan(_sample_ota_plan(), run_id="run_100")
        node = EdgeNode("node-01").attach_bus(broker)
        node.connect()

        broker.publish("swarm/node/node-01/ota", config.to_dict())

        self.assertIsNotNone(node.current_config)
        self.assertEqual(node.current_config["sampling_rate_hz"], 2)
        self.assertEqual(node.last_event()["event"], "config_applied")
        self.assertEqual(node.last_event()["status"], "accepted")

    def test_edge_node_rejects_invalid_payload(self):
        broker = InMemoryBroker()
        node = EdgeNode("node-02").attach_bus(broker)
        node.connect()

        broker.publish("swarm/node/node-02/ota", {"invalid": "payload"})

        self.assertIsNone(node.current_config)
        self.assertEqual(node.last_event()["event"], "config_rejected")
        self.assertEqual(node.last_event()["status"], "rejected")

    def test_canary_dispatch_publishes_to_selected_nodes(self):
        broker = InMemoryBroker()
        nodes = ["node-01", "node-02", "node-03", "node-04", "node-05"]
        config = build_ota_config_from_plan(_sample_ota_plan(), run_id="run_101")
        dispatch_report = dispatch_to_canary(
            broker=broker,
            config=config,
            node_ids=nodes,
            percentage=40,
            run_id="run_101",
        )

        self.assertEqual(dispatch_report["published"], 2)
        self.assertEqual(dispatch_report["target_nodes"], ["node-01", "node-02"])
        self.assertTrue(
            any(message["topic"].startswith("swarm/node/node-01/ota") for message in broker.published_messages)
        )

    def test_canary_dispatch_evaluation_promotes_when_applied_and_healthy(self):
        broker = InMemoryBroker()
        node_ids = ["node-01", "node-02", "node-03"]
        nodes = [EdgeNode(node_id=node_id).attach_bus(broker) for node_id in node_ids]
        for node in nodes:
            node.connect()

        config = build_ota_config_from_plan(_sample_ota_plan(), run_id="run_202")
        dispatch_report = dispatch_to_canary(
            broker=broker,
            config=config,
            node_ids=node_ids,
            percentage=34,
            run_id="run_202",
        )

        nodes[0].publish_telemetry(0.99)
        result = evaluate_canary_dispatch(
            dispatch_report=dispatch_report,
            nodes=nodes,
            telemetry_health_floor=0.95,
        )

        self.assertEqual(result["decision"], "promote")
        self.assertTrue(result["all_nodes_applied"])
        self.assertFalse(result["telemetry_violation"])
        self.assertEqual(result["telemetry_samples_total"], 1)

    def test_canary_dispatch_rolls_back_on_telemetry_violation(self):
        broker = InMemoryBroker()
        node_ids = ["node-01", "node-02", "node-03", "node-04"]
        nodes = [EdgeNode(node_id=node_id).attach_bus(broker) for node_id in node_ids]
        for node in nodes:
            node.connect()

        config = build_ota_config_from_plan(_sample_ota_plan(), run_id="run_203")
        dispatch_report = dispatch_to_canary(
            broker=broker,
            config=config,
            node_ids=node_ids,
            percentage=25,
            run_id="run_203",
        )

        nodes[0].publish_telemetry(0.82)
        result = evaluate_canary_dispatch(
            dispatch_report=dispatch_report,
            nodes=nodes,
            telemetry_health_floor=0.95,
        )

        self.assertEqual(result["decision"], "rollback")
        self.assertTrue(result["telemetry_violation"])

    def test_edge_node_rejects_non_dict_payload_without_crashing(self):
        broker = InMemoryBroker()
        node = EdgeNode("node-01").attach_bus(broker)
        node.connect()

        broker.publish("swarm/node/node-01/ota", [1, 2, 3])

        self.assertEqual(node.last_event()["event"], "config_rejected")
        self.assertIn("invalid_ota_payload", node.last_event()["reason"])


if __name__ == "__main__":
    unittest.main()
