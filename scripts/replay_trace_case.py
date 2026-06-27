from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.traces import load_trace, replay_trace_case


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay one recorded verification scenario.")
    parser.add_argument("trace", help="Path to trace JSON file")
    parser.add_argument("--scenario-id", required=True)
    args = parser.parse_args()

    trace = load_trace(args.trace)
    result = replay_trace_case(trace=trace, scenario_id=args.scenario_id)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

