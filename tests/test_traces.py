from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.test_verification import valid_plan
from swarmforge.scenarios import ScenarioSpec
from swarmforge.traces import (
    build_eval_case,
    build_verification_trace,
    load_trace,
    make_run_id,
    replay_trace_case,
    save_trace,
)
from swarmforge.verification import run_verification_matrix


def _scenario_specs_from_report(plan_report) -> tuple[ScenarioSpec, ...]:
    return tuple(ScenarioSpec(**spec) for spec in plan_report.executed_scenarios)


class TraceRecordTest(unittest.TestCase):
    def test_build_and_roundtrip_verification_trace(self):
        report = run_verification_matrix(valid_plan(), scenario_count=12, workers=2)
        trace = build_verification_trace(
            plan=valid_plan(),
            report=report,
            scenarios=_scenario_specs_from_report(report),
            run_id=make_run_id(),
            prompt="smoke test",
            model="gpt-5.5",
        )

        self.assertEqual(len(trace.scenario_records), len(report.case_results))

        with tempfile.TemporaryDirectory() as tmpdir:
            trace_path = Path(tmpdir) / "trace.json"
            save_trace(trace, trace_path)
            loaded = load_trace(trace_path)

        self.assertEqual(trace.to_dict(), loaded.to_dict())

    def test_replay_case_returns_matching_result(self):
        report = run_verification_matrix(valid_plan(), scenario_count=10, workers=1)
        trace = build_verification_trace(
            plan=valid_plan(),
            report=report,
            scenarios=_scenario_specs_from_report(report),
            run_id=make_run_id(),
            prompt="smoke test",
        )

        target_scenario_id = trace.scenario_records[0]["scenario"]["scenario_id"]
        replay = replay_trace_case(trace, scenario_id=target_scenario_id)

        self.assertTrue(replay["matches"])
        self.assertEqual(replay["requested_scenario_id"], target_scenario_id)

    def test_eval_case_can_export_failed_or_passed_snapshot(self):
        report = run_verification_matrix(valid_plan(), scenario_count=8, workers=1)
        trace = build_verification_trace(
            plan=valid_plan(),
            report=report,
            scenarios=_scenario_specs_from_report(report),
            run_id=make_run_id(),
            prompt="smoke test",
        )

        eval_case = build_eval_case(trace)
        self.assertIn("input", eval_case)
        self.assertIn("expected", eval_case)
        self.assertIn("metadata", eval_case)

        if trace.failed_scenario_ids:
            failed = trace.failed_scenario_ids[0]
            eval_failed = build_eval_case(trace, scenario_id=failed)
            self.assertEqual(eval_failed["input"]["scenario_id"], failed)

    def test_replay_unknown_scenario_raises(self):
        report = run_verification_matrix(valid_plan(), scenario_count=6, workers=1)
        trace = build_verification_trace(
            plan=valid_plan(),
            report=report,
            scenarios=_scenario_specs_from_report(report),
            run_id=make_run_id(),
            prompt="smoke test",
        )

        with self.assertRaises(KeyError):
            replay_trace_case(trace, scenario_id="unknown_scenario")


if __name__ == "__main__":
    unittest.main()

