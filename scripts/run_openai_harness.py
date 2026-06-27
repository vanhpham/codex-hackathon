from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmforge.env import load_env_file
from swarmforge.harness import OpenAIResponsesPlanClient, run_harness


DEFAULT_PROMPT = (
    "Xe dang vao vung bun lay, rung lac manh. "
    "Hay giam sample rate xuong 2Hz, them median filter cho gia toc, "
    "va chuyen log level sang WARNING."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Sprint 3 OpenAI harness path.")
    parser.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    load_env_file()
    result = run_harness(args.prompt, OpenAIResponsesPlanClient())
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
