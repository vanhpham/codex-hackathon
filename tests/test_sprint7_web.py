from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.sprint7_web import FleetController
from swarmforge.scenarios import ScenarioSpec
from swarmforge.traces import build_verification_trace, make_run_id, save_trace
from swarmforge.verification import run_verification_matrix
from tests.test_verification import valid_plan


def _build_trace_records() -> tuple[ScenarioSpec, ...]:
    report = run_verification_matrix(valid_plan(), scenario_count=6, workers=1)
    return tuple(ScenarioSpec(**spec) for spec in report.executed_scenarios), report


def _write_trace(tmpdir: str) -> str:
    scenarios, report = _build_trace_records()
    trace = build_verification_trace(
        plan=valid_plan(),
        report=report,
        scenarios=scenarios,
        run_id=make_run_id(),
        prompt="ui smoke",
    )
    path = Path(tmpdir) / f"{trace.run_id}.json"
    save_trace(trace, path)
    return trace.run_id


class Sprint7WebControllerTest(unittest.TestCase):
    def test_trace_listing_and_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = _write_trace(tmpdir)
            controller = FleetController(
                node_count=2,
                broker_mode="in-memory",
                telemetry_interval=3600.0,
                broker_host="localhost",
                broker_port=1883,
                telemetry_samples_per_node=1,
                node_prefix="n-",
                node_id_width=2,
                trace_dir=Path(tmpdir),
            )
            try:
                traces = controller.list_traces()
                self.assertEqual(len(traces), 1)
                self.assertEqual(traces[0]["run_id"], run_id)

                detail = controller.get_trace_detail(run_id)
                self.assertEqual(detail["run_id"], run_id)
                self.assertGreater(detail["scenario_count"], 0)
                self.assertIn("failed_cases", detail)

                trace_lookup, _ = controller.get_trace(run_id[:8])
                self.assertEqual(trace_lookup.run_id, run_id)
            finally:
                # Keep controller short-lived for test determinism.
                del controller

    def test_replay_uses_first_scenario_when_unspecified(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = _write_trace(tmpdir)
            controller = FleetController(
                node_count=2,
                broker_mode="in-memory",
                telemetry_interval=3600.0,
                broker_host="localhost",
                broker_port=1883,
                telemetry_samples_per_node=1,
                node_prefix="n-",
                node_id_width=2,
                trace_dir=Path(tmpdir),
            )
            try:
                traces = controller.list_traces()
                run = controller.get_trace_detail(run_id)
                self.assertGreater(run["scenario_count"], 0)
                first_scenario_id = run["scenario_records"][0]["scenario"]["scenario_id"]

                replay = controller.replay_trace(run_id)
                self.assertEqual(replay["requested_scenario_id"], first_scenario_id)
                self.assertIn("replayed_result", replay)
                self.assertIn("stored_result", replay)
                self.assertTrue(replay["matches"])
            finally:
                del controller


if __name__ == "__main__":
    unittest.main()
