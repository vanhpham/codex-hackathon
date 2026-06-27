from __future__ import annotations

import unittest

from swarmforge.ota import DispatchBlocked
from scripts import run_canary_demo as canary_script


class CanaryDemoTest(unittest.TestCase):
    def test_expand_health_inputs_repeats_single_value(self):
        self.assertEqual(
            canary_script.expand_health_inputs([0.96], 3),
            [0.96, 0.96, 0.96],
        )

    def test_expand_health_inputs_extends_tail(self):
        self.assertEqual(
            canary_script.expand_health_inputs([0.99, 0.98], 4),
            [0.99, 0.98, 0.98, 0.98],
        )

    def test_node_ids_width_control(self):
        self.assertEqual(
            canary_script.make_node_ids(3, prefix="n-", width=3),
            ["n-001", "n-002", "n-003"],
        )

    def test_run_canary_demo_promotes_when_safe(self):
        payload = canary_script.prepare_ready_payload()
        result = canary_script.run_canary_demo(
            ready_payload=payload,
            node_count=5,
            node_prefix="node-",
            node_id_width=2,
            health_values=[1.0],
        )
        self.assertEqual(result["evaluation"]["decision"], "promote")
        self.assertGreater(result["dispatch"]["published"], 0)
        self.assertIsNotNone(result["evaluation"]["telemetry_input"])

    def test_invalid_payload_is_blocked(self):
        blocked_payload = {
            "run_id": "run_blocked",
            "status": "schema_rejected",
            "plan_status": "invalid",
            "simulation_status": "not_started",
            "deployment_decision": "blocked",
        }

        with self.assertRaises(DispatchBlocked):
            canary_script.run_canary_demo(
                ready_payload=blocked_payload,
                node_count=3,
                node_prefix="node-",
                node_id_width=2,
            )


if __name__ == "__main__":
    unittest.main()
