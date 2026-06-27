# Sprint 6: MQTT Edge Loop And Canary Runtime

Sprint 6 turns a verified `ready_for_canary` risk report into a bounded OTA configuration update for virtual edge nodes.

MQTT is no longer the first deep engineering milestone. It is the runtime proof after the verification harness has already shown that the plan is safe enough to canary.

The Sprint 6 thesis:

```text
Only verification-approved plans become OTA configs.
The model never publishes MQTT messages directly.
```

## Sprint Goal

Build the first local edge loop:

```text
ready_for_canary RiskReport
  -> trusted OTA config payload
  -> MQTT canary topic
  -> one edge node applies config at runtime
  -> edge node publishes telemetry/events
```

Sprint 6 establishes the runtime boundary. It should not bypass Sprint 4 verification.

Sprint 6 now uses a real MQTT path locally:

- Mosquitto via `docker/docker-compose.yml`
- Runtime transport via Docker CLI (`swarmforge.mqtt_transport`)
- Dashboard in `scripts/sprint7_web.py` (alias `scripts/sprint6_web.py`)
- Optional standalone node process in `scripts/mqtt_node_agent.py`

## Inputs

Sprint 6 consumes only verification-approved results:

```text
verification_status: passed
risk_score: below threshold
decision: ready_for_canary
```

Any schema rejection, simulator rejection, verification failure, or high-risk report must be blocked before MQTT dispatch.

## MQTT Topic Contract

```text
swarm/control/ota
swarm/node/{node_id}/ota
swarm/telemetry/{node_id}
swarm/events/{node_id}
```

Recommended usage:

- `swarm/control/ota`: fleet-wide command channel, not used for first canary dispatch.
- `swarm/node/{node_id}/ota`: targeted OTA config for one node.
- `swarm/telemetry/{node_id}`: node telemetry snapshots.
- `swarm/events/{node_id}`: config applied, rollback, exception, health events.

## OTA Config Payload

The backend maps the verified `OptimizationPlan` to a trusted runtime config:

```json
{
  "config_version": "cfg_001",
  "source_run_id": "run_001",
  "sampling_rate_hz": 2,
  "log_level": "WARNING",
  "filter": {
    "type": "median",
    "window_size": 5
  },
  "telemetry_collection": {
    "metrics": ["accelerometer", "temperature", "battery"],
    "aggregation_window_seconds": 5,
    "publish_mode": "summary_and_anomalies",
    "max_payload_kbps": 8
  },
  "rollback": {
    "enabled": true,
    "max_latency_ms": 250,
    "max_error_rate": 0.02,
    "min_telemetry_health": 0.95
  }
}
```

The payload should contain only trusted config fields. It should not include arbitrary code.

## Edge Node Behavior

Each virtual edge node should:

- start with baseline config
- publish telemetry at current `sampling_rate_hz`
- subscribe to `swarm/node/{node_id}/ota`
- validate incoming OTA config
- apply config without process restart
- publish `config_applied` event on success
- publish `config_rejected` event on invalid config

## Canary Runtime

Initial canary can be simple:

```text
fleet_size: configurable
canary_percentage: from plan deployment percentage
canary_nodes: first N sorted node ids
```

The first implementation only needs targeted dispatch. Promotion/rollback automation can be expanded after telemetry feedback is stable.

## Test Scenarios

| Scenario | Input | Expected Result |
| --- | --- | --- |
| Ready report | `ready_for_canary` risk report | OTA payload created |
| Rejected report | high-risk or blocked report | MQTT dispatch blocked |
| Canary selection | 10 nodes, 5% | one canary node |
| Topic mapping | `node-01` | `swarm/node/node-01/ota` |
| Edge apply | valid OTA payload | config updated and event emitted |

## Local Commands

Unit tests:

```text
.venv/bin/python -m unittest
```

Local canary demo:

```bash
.venv/bin/python scripts/run_canary_demo.py
```

Canary demo from a saved trace:

```bash
.venv/bin/python scripts/run_canary_demo.py --trace traces/<run_id>.json --node-count 10
```

## Sprint 6 Runtime (Docker + Web)

Start full local stack (broker + dashboard + standalone edge-node agents):

```bash
docker compose -f docker/docker-compose.yml up -d --build
```
Stop stack:

```bash
docker compose -f docker/docker-compose.yml down
```

Override defaults with env:

```bash
SWARM_NODE_COUNT=12 SWARM_TELEMETRY_INTERVAL=1.0 \
SWARM_HEALTH_CURVE=steady \
docker compose -f docker/docker-compose.yml up -d --build
```

Default dashboard nodes (for UI runtime) still use `node-*` IDs.
Standalone agents use `edge-*` IDs so they don't collide with dashboard targets.

## Definition Of Done

Sprint 6 is complete when:

- A verification-approved result can be converted to OTA config.
- Rejected/high-risk reports cannot be dispatched.
- Canary node selection is deterministic.
- MQTT topics are generated consistently.
- One edge node can apply an OTA config without restart.
- Tests cover config mapping, dispatch blocking, canary selection, and edge apply logic.
- Demo output includes canary decision (`promote`/`rollback`) from applied telemetry health.
- Docker MQTT + web dashboard + node path is runnable end-to-end (with optional standalone node agents).

## Stretch Handoff

After Sprint 6:

```text
multi-node swarm -> promotion monitor -> rollback automation -> dashboard integration
```
