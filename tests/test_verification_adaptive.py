from __future__ import annotations

import unittest
from unittest.mock import patch

from swarmforge.scenarios import ScenarioSpec
from swarmforge.verification import run_verification_matrix
from tests.test_verification import valid_plan


class VerificationAdaptiveTest(unittest.TestCase):
    def test_adaptive_round_adds_candidate_cases(self):
        candidates = (
            ScenarioSpec(
                scenario_id="adaptive_test_1",
                seed=301,
                duration_seconds=30,
                baseline_sample_rate_hz=10,
                terrain="muddy",
                noise_level="high",
                network_profile="high_loss",
                battery_state="critical",
                sensor_fault="dropout",
                fleet_size=100,
            ),
            ScenarioSpec(
                scenario_id="adaptive_test_2",
                seed=302,
                duration_seconds=30,
                baseline_sample_rate_hz=10,
                terrain="rocky",
                noise_level="high",
                network_profile="high_loss",
                battery_state="critical",
                sensor_fault="dropout",
                fleet_size=100,
            ),
        )
        base_fail_case = (
            ScenarioSpec(
                scenario_id="forced_fail_case",
                seed=99,
                duration_seconds=30,
                baseline_sample_rate_hz=1,
                terrain="muddy",
                noise_level="high",
                network_profile="high_loss",
                battery_state="critical",
                sensor_fault="dropout",
                fleet_size=100,
            ),
        )

        with patch("swarmforge.verification.generate_counterexample_candidates", return_value=candidates):
            report = run_verification_matrix(
                plan=valid_plan(),
                scenarios=base_fail_case,
                enable_adaptive=True,
                adaptive_rounds=1,
                adaptive_budget=2,
                workers=1,
            )

        self.assertGreaterEqual(report.scenario_count, 3)
        self.assertEqual(report.adaptive_cycles, 1)
        self.assertEqual(set(candidates[i].scenario_id for i in range(len(candidates))).issubset(set(report.candidate_scenarios)), True)

    def test_adaptive_disabled_keeps_candidate_metadata_zero(self):
        report = run_verification_matrix(
            plan=valid_plan(),
            scenario_count=8,
            enable_adaptive=False,
            workers=1,
        )

        self.assertEqual(report.adaptive_cycles, 0)
        self.assertEqual(report.candidate_scenarios, ())

    def test_worker_pool_is_deterministic(self):
        report_single = run_verification_matrix(
            plan=valid_plan(),
            scenario_count=20,
            workers=1,
            seed_start=3,
        )
        report_multi = run_verification_matrix(
            plan=valid_plan(),
            scenario_count=20,
            workers=4,
            seed_start=3,
        )

        self.assertEqual(report_single.pass_rate, report_multi.pass_rate)
        self.assertEqual(report_single.risk_score, report_multi.risk_score)
        self.assertEqual(report_single.scenario_count, report_multi.scenario_count)


if __name__ == "__main__":
    unittest.main()
