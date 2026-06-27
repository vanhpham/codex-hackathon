from __future__ import annotations

import unittest

from swarmforge.risk import RiskReport, SettingSuggestionReport
from swarmforge.schemas import FilterSpec, OptimizationPlan, RollbackPolicy, TelemetryCollection, DeploymentSpec
from swarmforge.setting_suggester import suggest_setting_adjustments


def _example_plan() -> OptimizationPlan:
    return OptimizationPlan(
        intent="reduce_noise_and_bandwidth",
        target_metric="accelerometer",
        sampling_rate_hz=8,
        log_level="WARNING",
        filter=FilterSpec(type="median", window_size=7),
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


def _highly_constrained_ready_plan() -> OptimizationPlan:
    return OptimizationPlan(
        intent="reduce_noise_and_bandwidth",
        target_metric="accelerometer",
        sampling_rate_hz=1,
        log_level="WARNING",
        filter=FilterSpec(type="median", window_size=15),
        telemetry_collection=TelemetryCollection(
            metrics=("accelerometer", "temperature", "battery"),
            aggregation_window_seconds=5,
            publish_mode="summary_and_anomalies",
            max_payload_kbps=64,
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


def _blocked_report() -> RiskReport:
    return RiskReport(
        verification_status="failed",
        scenario_count=12,
        passed_count=8,
        failed_count=4,
        pass_rate=0.6667,
        risk_score=0.67,
        worst_case={"scenario_id": "s1", "telemetry_health": 0.7, "score": 0.5, "accepted": False},
        failed_scenarios=("s1", "s2"),
        critical_failures=("telemetry_health_above_floor", "latency_within_budget"),
        decision="blocked",
        case_results=(),
    )


class SettingSuggesterTest(unittest.TestCase):
    def test_blocked_report_returns_mutually_exclusive_options(self):
        report = _blocked_report()
        suggestions = suggest_setting_adjustments(_example_plan(), report, max_suggestions=2)

        self.assertIsInstance(suggestions, SettingSuggestionReport)
        self.assertEqual(len(suggestions.mutually_exclusive_options), 2)
        self.assertTrue(any("latency" in option["description"] for option in suggestions.mutually_exclusive_options))
        self.assertTrue(any("sample" in option["description"] for option in suggestions.mutually_exclusive_options))
        self.assertIn("risk_score_delta", suggestions.risk_delta_preview)

    def test_safe_suggestions_do_not_violate_constraints(self):
        report = _blocked_report()
        suggestions = suggest_setting_adjustments(_example_plan(), report, max_suggestions=3)

        self.assertLessEqual(len(suggestions.mutually_exclusive_options), 3)
        for option in suggestions.mutually_exclusive_options:
            changes = option["changes"]
            if "sampling_rate_hz" in changes:
                self.assertGreaterEqual(changes["sampling_rate_hz"], 1)
                self.assertLessEqual(changes["sampling_rate_hz"], 20)
            if "filter" in changes:
                self.assertIn(changes["filter"]["type"], {"moving_average", "median", "low_pass", "none"})
                self.assertGreaterEqual(changes["filter"]["window_size"], 1)
                self.assertLessEqual(changes["filter"]["window_size"], 15)
                if changes["filter"]["type"] == "median":
                    self.assertEqual(changes["filter"]["window_size"] % 2, 1)
            if "telemetry_collection" in changes:
                self.assertGreaterEqual(changes["telemetry_collection"]["max_payload_kbps"], 1)
                self.assertLessEqual(changes["telemetry_collection"]["max_payload_kbps"], 64)
            if "deployment" in changes:
                self.assertGreaterEqual(changes["deployment"]["percentage"], 1)
                self.assertLessEqual(changes["deployment"]["percentage"], 20)

    def test_ready_plan_keeps_options_minimal(self):
        plan = _highly_constrained_ready_plan()
        report = RiskReport(
            verification_status="passed",
            scenario_count=20,
            passed_count=20,
            failed_count=0,
            pass_rate=0.99,
            risk_score=0.01,
            worst_case={"scenario_id": "s", "telemetry_health": 1.0, "score": 0.9, "accepted": True},
            failed_scenarios=(),
            critical_failures=(),
            decision="ready_for_canary",
            case_results=(),
        )

        suggestions = suggest_setting_adjustments(plan, report)

        self.assertIn("no immediate adjustment", suggestions.reason)

    def test_llm_suggestions_are_merged_when_available(self):
        class FakeLLMClient:
            def generate_setting_suggestions(self, prompt: str) -> dict[str, object]:
                del prompt
                return {
                    "reason": "Prefer tighter bandwidth profile for throughput.",
                    "confidence": 0.81,
                    "options": [
                        {
                            "description": "Lower payload cap and increase aggregation under jitter.",
                            "rationale": "reduce publish pressure and retries.",
                            "changes": {
                                "telemetry_collection": {
                                    "max_payload_kbps": 4.0,
                                    "aggregation_window_seconds": 10,
                                },
                            },
                            "expected_pass_rate_delta": 0.02,
                            "expected_risk_score_delta": -0.03,
                        },
                    ],
                }

        suggestions = suggest_setting_adjustments(
            _example_plan(),
            _blocked_report(),
            max_suggestions=6,
            client=FakeLLMClient(),
            use_llm=True,
        )

        self.assertGreaterEqual(len(suggestions.mutually_exclusive_options), 3)
        self.assertTrue(any(option.get("source") == "llm" for option in suggestions.mutually_exclusive_options))
        self.assertLessEqual(len(suggestions.mutually_exclusive_options), 6)

    def test_invalid_llm_payload_falls_back(self):
        class BadLLMClient:
            def generate_setting_suggestions(self, prompt: str) -> dict[str, object]:
                del prompt
                return {"reason": "bad"}

        suggestions = suggest_setting_adjustments(
            _example_plan(),
            _blocked_report(),
            client=BadLLMClient(),
            use_llm=True,
        )

        self.assertIsInstance(suggestions, SettingSuggestionReport)
        self.assertGreater(len(suggestions.mutually_exclusive_options), 0)
        self.assertTrue("blocked run can improve" in suggestions.reason.lower())


if __name__ == "__main__":
    unittest.main()
