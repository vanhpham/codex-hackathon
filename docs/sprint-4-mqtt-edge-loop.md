# Sprint 4: MQTT Edge Loop and Canary Foundation

Sprint 4 turns a `ready_for_canary` harness result into a bounded OTA configuration update for virtual edge nodes.

The Sprint 4 thesis:

```text
Only harness-approved plans become OTA configs.
The model never publishes MQTT messages directly.
```

## Sprint Goal

Build the first local edge loop:

```text
ready_for_canary HarnessResult
  -> trusted OTA config payload
  -> MQTT canary topic
  -> one edge node applies config at runtime
  -> edge node publishes telemetry/events
```

Sprint 4 should establish the runtime boundary for deployment. It does not need the final dashboard yet.

## Inputs

Sprint 4 consumes only accepted Sprint 3 results:

```text
status: ready_for_canary
plan_status: valid
simulation_status: accepted
deployment_decision: ready_for_canary
```

Any `schema_rejected` or `simulation_rejected` result must be blocked before MQTT dispatch.

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

The backend maps `OptimizationPlan` to a trusted runtime config:

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

## Canary Foundation

Initial Sprint 4 canary can be simple:

```text
fleet_size: configurable
canary_percentage: from plan deployment percentage
canary_nodes: first N sorted node ids
```

The first implementation only needs targeted dispatch. Promotion/rollback automation can be expanded after one-node MQTT is stable.

## Test Scenarios

| Scenario | Input | Expected Result |
| --- | --- | --- |
| Ready plan | `ready_for_canary` result | OTA payload created |
| Rejected plan | `simulation_rejected` result | MQTT dispatch blocked |
| Canary selection | 10 nodes, 5% | one canary node |
| Topic mapping | `node-01` | `swarm/node/node-01/ota` |
| Edge apply | valid OTA payload | config updated and event emitted |

## Local Commands

Unit tests:

```text
.venv/bin/python -m unittest
```

Future live MQTT smoke test:

```text
docker compose up mqtt
.venv/bin/python edge_node/edge_agent.py --node-id node-01
```

## Definition of Done

Sprint 4 is complete when:

- A `ready_for_canary` result can be converted to OTA config.
- Rejected harness results cannot be dispatched.
- Canary node selection is deterministic.
- MQTT topics are generated consistently.
- One edge node can apply an OTA config without restart.
- Tests cover config mapping, dispatch blocking, canary selection, and edge apply logic.

## Sprint 5 Handoff

Sprint 5 should add dashboard and trace/eval polish:

```text
telemetry/events -> WebSocket/dashboard -> run timeline -> trace/eval records
```
