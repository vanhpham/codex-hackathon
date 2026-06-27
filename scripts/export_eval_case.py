from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.traces import build_eval_case, load_trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Export eval-style fixture from trace.")
    parser.add_argument("trace", help="Path to trace JSON file")
    parser.add_argument("--scenario-id", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    trace = load_trace(args.trace)
    payload = build_eval_case(trace, scenario_id=args.scenario_id)

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Saved eval case to {path}")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

