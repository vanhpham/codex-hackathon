from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.schemas import OptimizationPlan
from swarmforge.verification import DEFAULT_ADAPTIVE_WORKERS, run_verification_matrix
from swarmforge.scenarios import ScenarioSpec, generate_scenario_matrix
from swarmforge.setting_suggester import suggest_setting_adjustments
from swarmforge.traces import build_verification_trace, make_run_id, save_trace


SAMPLE_PLAN = {
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Sprint 4 verification matrix.")
    parser.add_argument("--scenario-count", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--adaptive", action="store_true")
    parser.add_argument("--workers", type=int, default=DEFAULT_ADAPTIVE_WORKERS)
    parser.add_argument("--adaptive-rounds", type=int, default=1)
    parser.add_argument("--adaptive-budget", type=int, default=20)
    parser.add_argument("--suggest-settings", action="store_true")
    parser.add_argument("--max-suggestions", type=int, default=3)
    parser.add_argument("--trace-dir", default=".swarmforge_traces")
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--no-trace", action="store_true")
    args = parser.parse_args()

    plan = OptimizationPlan.from_dict(SAMPLE_PLAN)
    scenarios = generate_scenario_matrix(
        count=args.scenario_count,
        seed_start=args.seed_start,
    )
    report = run_verification_matrix(
        plan=plan,
        scenarios=scenarios,
        enable_adaptive=args.adaptive,
        workers=args.workers,
        adaptive_rounds=args.adaptive_rounds,
        adaptive_budget=args.adaptive_budget,
        seed_start=args.seed_start,
    )
    setting_suggestions = None
    setting_suggestion_report = None

    payload = {
        "verification": report.to_dict(),
    }

    if args.suggest_settings:
        setting_suggestion_report = suggest_setting_adjustments(
            plan=plan,
            report=report,
            max_suggestions=args.max_suggestions,
        )
        setting_suggestions = setting_suggestion_report.to_dict()
        payload["setting_suggestions"] = setting_suggestions

    if not args.no_trace:
        trace = build_verification_trace(
            plan=plan,
            report=report,
            scenarios=(
                tuple(ScenarioSpec(**spec) for spec in report.executed_scenarios)
                if report.executed_scenarios
                else tuple(scenarios)
            ),
            run_id=args.trace_id or make_run_id(),
            model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
            prompt="local verification matrix demo",
            setting_suggestion=setting_suggestion_report,
        )
        trace_path = Path(args.trace_dir) / f"{trace.run_id}.json"
        save_trace(trace, trace_path)
        payload["trace"] = {
            "run_id": trace.run_id,
            "path": str(trace_path),
        }

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
