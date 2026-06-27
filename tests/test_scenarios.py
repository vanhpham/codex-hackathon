from __future__ import annotations

import json
import unittest

from swarmforge.risk import InvariantFailure, RiskReport, VerificationCaseResult
from swarmforge.scenarios import generate_scenario_matrix, scenario_signal


class ScenarioModelTest(unittest.TestCase):
    def test_scenario_matrix_is_deterministic(self):
        first = generate_scenario_matrix(count=8, seed_start=10)
        second = generate_scenario_matrix(count=8, seed_start=10)

        self.assertEqual([scenario.to_dict() for scenario in first], [scenario.to_dict() for scenario in second])
        self.assertEqual(first[0].scenario_id, "muddy_high_stable_normal_none_seed_10")

    def test_scenario_signal_is_replayable(self):
        scenario = generate_scenario_matrix(count=1, seed_start=42)[0]

        self.assertEqual(scenario_signal(scenario), scenario_signal(scenario))

    def test_risk_report_is_json_serializable(self):
        result = VerificationCaseResult(
            scenario_id="scenario_1",
            accepted=False,
            failed_invariants=(
                InvariantFailure(
                    name="telemetry_health_above_floor",
                    reason="Telemetry health fell below floor.",
                ),
            ),
            metrics={"telemetry_health": 0.7},
            reason="Telemetry health fell below floor.",
        )
        report = RiskReport(
            verification_status="failed",
            scenario_count=1,
            passed_count=0,
            failed_count=1,
            pass_rate=0,
            risk_score=1,
            worst_case={"scenario_id": "scenario_1"},
            failed_scenarios=("scenario_1",),
            critical_failures=(),
            decision="blocked",
            case_results=(result,),
        )

        encoded = json.dumps(report.to_dict(), sort_keys=True)

        self.assertIn("telemetry_health_above_floor", encoded)


if __name__ == "__main__":
    unittest.main()
