from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_node_ids(prefix: str, count: int, width: int) -> list[str]:
    return [f"{prefix}{index:0{width}d}" for index in range(1, count + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multiple MQTT edge-node agents.")
    parser.add_argument("--node-count", type=int, default=5)
    parser.add_argument("--broker-host", default="localhost")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--telemetry-interval", type=float, default=1.5)
    parser.add_argument("--health-curve", choices=["healthy", "steady", "noisy"], default="healthy")
    parser.add_argument("--health-floor", type=float, default=0.95)
    parser.add_argument("--node-prefix", default="node-")
    parser.add_argument("--node-id-width", type=int, default=2)
    args = parser.parse_args()

    python = sys.executable
    agent = str(ROOT / "scripts" / "mqtt_node_agent.py")
    node_ids = _build_node_ids(args.node_prefix, args.node_count, args.node_id_width)
    processes: list[subprocess.Popen[str]] = []

    try:
        for node_id in node_ids:
            proc = subprocess.Popen(
                [
                    python,
                    agent,
                    "--node-id",
                    node_id,
                    "--broker-host",
                    args.broker_host,
                    "--broker-port",
                    str(args.broker_port),
                    "--telemetry-interval",
                    str(args.telemetry_interval),
                    "--health-curve",
                    args.health_curve,
                    "--health-floor",
                    str(args.health_floor),
                ],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            processes.append(proc)
            print(f"[launch] started {node_id} pid={proc.pid}")

        print("Press Ctrl+C to stop all sprint-6 node agents.")
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping sprint-6 node agents ...")
    finally:
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait(timeout=2)


if __name__ == "__main__":
    main()
