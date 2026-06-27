from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.schemas import OptimizationPlan
from swarmforge.scenarios import generate_scenario_matrix
from swarmforge.verification import run_verification_matrix


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
    args = parser.parse_args()

    plan = OptimizationPlan.from_dict(SAMPLE_PLAN)
    scenarios = generate_scenario_matrix(
        count=args.scenario_count,
        seed_start=args.seed_start,
    )
    report = run_verification_matrix(
        plan=plan,
        scenarios=scenarios,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
