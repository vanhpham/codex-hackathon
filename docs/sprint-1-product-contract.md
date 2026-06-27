# Sprint 1: Product Contract and Schema Gate

Sprint 1 defines the product contract for SwarmForge Harness before runtime code is built. The output of this sprint is a clear, judge-friendly harness specification and a schema-first contract that future backend, simulator, MQTT, and dashboard work must follow.

The core promise remains:

```text
Natural-language engineering request
  -> structured optimization plan
  -> schema validation
  -> local simulation
  -> canary deployment
  -> telemetry monitoring
  -> rollback decision
  -> trace/eval record
```

The LLM proposes. The harness decides.

## Sprint Goal

Create the first stable product and data contract for a safe OTA tuning harness.

By the end of Sprint 1, the team should be able to answer:

- What exact problem does the demo solve?
- What is the first end-to-end scenario?
- What object is the LLM allowed to produce?
- What object is the harness responsible for validating?
- Which plan fields are accepted, bounded, or rejected?
- What output shape should later phases return to the dashboard and trace store?

## Non-Goals

Sprint 1 does not include:

- FastAPI scaffolding.
- OpenAI API integration.
- MQTT setup.
- Edge node containers.
- Dashboard implementation.
- Generated Python filters.
- Docker Compose runtime.

Those belong to later sprints after the schema contract is approved.

## Demo Scenario

Baseline swarm state:

```text
Domain: off-road racing / harsh terrain edge telemetry
Fleet: virtual edge nodes
Signal: noisy accelerometer stream
Baseline sample rate: 10 Hz
Baseline log level: INFO
Baseline filter: none
Problem: high noise, high bandwidth, higher battery drain
```

Engineer request:

```text
Xe dang vao vung bun lay, rung lac manh. Hay giam sample rate xuong 2Hz,
them median filter cho gia toc, va chuyen log level sang WARNING.
```

Expected harness behavior:

```text
1. Convert the request into a structured optimization plan.
2. Validate the plan against a strict schema and safety policy.
3. Defer all runtime decisions to the harness, not the model.
4. Prepare the plan for simulation in Sprint 2.
```

## Product Contract

The LLM may produce:

- intent classification
- target metric
- sample rate target
- filter specification
- log level
- deployment strategy request
- rollback policy request
- human-readable rationale

The LLM may not:

- deploy directly to nodes
- call MQTT directly
- execute arbitrary code
- generate Python filter code for MVP
- bypass canary
- request full-fleet deployment as the first action
- disable rollback

The harness owns:

- schema validation
- policy validation
- trusted filter implementation mapping
- simulation
- scoring
- canary selection
- OTA dispatch
- health monitoring
- rollback
- trace/eval persistence

## OptimizationPlan Draft

This is the canonical object the model should return through Structured Outputs in a later sprint.

```json
{
  "intent": "reduce_noise_and_bandwidth",
  "target_metric": "accelerometer",
  "sampling_rate_hz": 2,
  "log_level": "WARNING",
  "filter": {
    "type": "median",
    "window_size": 5
  },
  "deployment": {
    "strategy": "canary",
    "percentage": 5,
    "observation_window_seconds": 10
  },
  "rollback": {
    "enabled": true,
    "max_latency_ms": 250,
    "max_error_rate": 0.02,
    "min_telemetry_health": 0.95
  },
  "rationale": "Reduce noisy accelerometer readings and lower bandwidth while preserving a bounded rollout."
}
```

## Field Requirements

### `intent`

Allowed values:

```text
reduce_noise
reduce_bandwidth
reduce_noise_and_bandwidth
improve_battery_life
stabilize_telemetry
```

Requirement:

- Required.
- Must map to a measurable simulator goal in Sprint 2.

### `target_metric`

Allowed values:

```text
accelerometer
temperature
battery
bandwidth
telemetry_health
```

Requirement:

- Required.
- MVP demo should use `accelerometer`.

### `sampling_rate_hz`

Requirement:

- Required.
- Integer or number.
- Minimum: `1`.
- Maximum: `20`.
- MVP recommended target: `2`.

Reject examples:

```text
0
0.1
50
"fast"
```

### `log_level`

Allowed values:

```text
DEBUG
INFO
WARNING
ERROR
```

Requirement:

- Required.
- MVP target should use `WARNING`.

### `filter`

Allowed filter types:

```text
none
moving_average
median
low_pass
```

Requirements:

- Required.
- `filter.type` must be allowlisted.
- `window_size` is required for `moving_average` and `median`.
- `window_size` must be odd for `median`.
- `window_size` minimum: `1`.
- `window_size` maximum: `15`.
- `low_pass` may later use `alpha`, but alpha is out of scope for Sprint 1 MVP validation.

Recommended MVP filter:

```json
{
  "type": "median",
  "window_size": 5
}
```

### `deployment`

Allowed strategies:

```text
canary
shadow
full_after_canary
```

Requirements:

- Required.
- First runtime deployment must be `canary`.
- First deployment percentage must be between `1` and `20`.
- MVP recommended percentage: `5`.
- Observation window should be between `5` and `30` seconds.

Reject examples:

```json
{
  "strategy": "full_fleet",
  "percentage": 100
}
```

```json
{
  "strategy": "canary",
  "percentage": 80
}
```

### `rollback`

Requirements:

- Required.
- `enabled` must be `true` for MVP.
- Must include at least one measurable health threshold.
- Rollback cannot be disabled by the LLM.

Suggested thresholds:

```text
max_latency_ms: 50..1000
max_error_rate: 0..0.2
min_telemetry_health: 0.8..1.0
```

## Validation Result Contract

The schema gate should return a machine-readable result.

Accepted example:

```json
{
  "accepted": true,
  "stage": "schema_gate",
  "reasons": [],
  "normalized_plan": {
    "intent": "reduce_noise_and_bandwidth",
    "target_metric": "accelerometer",
    "sampling_rate_hz": 2,
    "log_level": "WARNING",
    "filter": {
      "type": "median",
      "window_size": 5
    },
    "deployment": {
      "strategy": "canary",
      "percentage": 5,
      "observation_window_seconds": 10
    },
    "rollback": {
      "enabled": true,
      "max_latency_ms": 250,
      "max_error_rate": 0.02,
      "min_telemetry_health": 0.95
    }
  }
}
```

Rejected example:

```json
{
  "accepted": false,
  "stage": "schema_gate",
  "reasons": [
    "sampling_rate_hz must be between 1 and 20",
    "first deployment must use canary",
    "rollback.enabled must be true"
  ],
  "normalized_plan": null
}
```

## Harness Run State Draft

Future phases should expose a run state that can drive both the dashboard and trace records.

```json
{
  "run_id": "run_001",
  "status": "schema_validated",
  "prompt": "Reduce noisy accelerometer telemetry and sample at 2Hz.",
  "model_plan": {},
  "schema_result": {},
  "simulation_result": null,
  "deployment_decision": "not_started",
  "canary_result": null,
  "rollback_result": null,
  "created_at": "2026-06-27T00:00:00Z"
}
```

Allowed run statuses:

```text
created
plan_generated
schema_validated
schema_rejected
simulation_running
simulation_rejected
ready_for_canary
canary_running
canary_failed
rollback_triggered
promoted
completed
failed
```

## Sprint 1 Backlog

| Item | Requirement | Output |
| --- | --- | --- |
| Product promise | Define the one-sentence demo promise | README/docs language |
| Demo scenario | Define baseline, operator request, expected safe result | Scenario contract |
| LLM boundary | List what model may and may not do | Safety contract |
| Schema draft | Define OptimizationPlan fields and constraints | JSON examples |
| Validation result | Define accepted/rejected output shape | Result contract |
| Run state | Define future trace/dashboard state shape | HarnessRun draft |
| Approval checkpoint | Confirm schema before coding | Sprint 1 sign-off |

## Definition of Done

Sprint 1 is complete when:

- The product contract is written down.
- The MVP demo scenario is explicit.
- The LLM boundary is clear.
- `OptimizationPlan` fields and constraints are agreed.
- Validation accepted/rejected output shapes are agreed.
- Future simulator and backend work can consume this contract.
- No runtime implementation has been started without approval.

## Sprint 2 Handoff

Sprint 2 should consume this contract and build the local simulator.

Simulator input:

```text
OptimizationPlan
baseline synthetic accelerometer signal
baseline fleet config
```

Simulator output:

```text
noise_score_before
noise_score_after
bandwidth_before_kbps
bandwidth_after_kbps
latency_penalty_ms
accepted
reason
```

The key Sprint 2 question:

```text
Does a schema-valid plan actually improve measured behavior before deployment?
```
