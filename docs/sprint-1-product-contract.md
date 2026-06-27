# Sprint 1: Product Contract And Typed Control Plan

Sprint 1 defines SwarmForge as an AI-assisted verification control plane, not a chatbot and not a direct deployment tool.

The core promise:

```text
Natural-language engineering intent
  -> typed operational control plan
  -> schema and policy gate
  -> verification before deployment
```

The model proposes. The harness verifies. The harness decides.

## Sprint Goal

Create the first stable product and data contract:

- what problem the system solves
- what the LLM may propose
- what the harness owns
- which operational knobs are allowed
- which safety policies are non-negotiable
- what output shape downstream verification consumes

## Track Fit

The hackathon track rewards engineering depth. The Sprint 1 framing must make clear that SwarmForge is not "AI changes config." It is:

```text
AI-assisted plan generation + harness-owned verification + auditable safety decisions.
```

The project should feel like a control-plane compiler and verification lab.

## Demo Scenario

Baseline edge swarm:

```text
Domain: off-road racing / harsh terrain telemetry
Fleet: virtual edge nodes
Signal: noisy accelerometer stream
Baseline sample rate: 10 Hz
Baseline filter: none
Baseline telemetry mode: raw
Baseline log level: INFO
Problem: noisy signal, high bandwidth, higher battery drain
```

Engineer request:

```text
Xe dang vao vung bun lay, rung lac manh. Hay giam sample rate xuong 2Hz,
them median filter cho gia toc, va chuyen log level sang WARNING.
```

Expected behavior:

```text
1. OpenAI proposes a typed OptimizationPlan.
2. Harness validates schema and policy.
3. Harness prepares the plan for verification.
4. Later sprints stress-test the plan across many scenarios.
```

## Model Boundary

The LLM may produce:

- intent classification
- target metric
- operational knob changes
- deployment strategy request
- rollback policy request
- human-readable rationale

The LLM may not:

- deploy directly
- publish MQTT messages
- execute arbitrary code
- generate Python filters for MVP
- bypass canary
- request full rollout as the first action
- disable rollback
- override verification results

## Harness Responsibilities

The harness owns:

- schema validation
- policy validation
- trusted implementation mapping
- deterministic simulation
- adversarial scenario generation
- safety invariant checks
- risk scoring
- canary decision
- trace/eval persistence
- rollback enforcement

## Control Knobs

The typed control plan should support more than basic config fields.

| Area | Allowed Knobs |
| --- | --- |
| Telemetry | `sampling_rate_hz`, `metrics`, `aggregation_window_seconds`, `publish_mode`, `max_payload_kbps` |
| Signal processing | `filter.type`, `filter.window_size`, future `low_pass.alpha` |
| Power | `power_mode`, `duty_cycle`, `sleep_interval_ms` |
| Network | `batching_window_ms`, `compression`, `retry_policy`, `mqtt_qos` |
| Logging | `log_level`, `event_sample_rate`, `error_only_mode` |
| Anomaly detection | `threshold`, `debounce_window`, `alert_severity` |
| Deployment | `strategy`, `percentage`, `observation_window_seconds`, `rollout_ring` |
| Rollback | `enabled`, `max_latency_ms`, `max_error_rate`, `min_telemetry_health` |

MVP implementation may start with telemetry, signal processing, deployment, and rollback. The docs should keep the broader control-plane direction visible.

## OptimizationPlan Draft

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
  "telemetry_collection": {
    "metrics": ["accelerometer", "temperature", "battery"],
    "aggregation_window_seconds": 5,
    "publish_mode": "summary_and_anomalies",
    "max_payload_kbps": 8
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
  "rationale": "Reduce noisy accelerometer readings and bandwidth while preserving a bounded rollout."
}
```

## Non-Negotiable Policies

- `sampling_rate_hz` must be `1..20`.
- `filter.type` must be `none`, `moving_average`, `median`, or `low_pass`.
- `filter.window_size` must be `1..15`.
- First deployment must be `canary`.
- First canary percentage must be `1..20`.
- Rollback must be enabled.
- Telemetry payload cap must be bounded.
- No arbitrary code execution in MVP.

## Validation Result Contract

Accepted:

```json
{
  "accepted": true,
  "stage": "schema_gate",
  "reasons": [],
  "normalized_plan": {}
}
```

Rejected:

```json
{
  "accepted": false,
  "stage": "schema_gate",
  "reasons": [
    "first deployment must use canary",
    "rollback.enabled must be true"
  ],
  "normalized_plan": null
}
```

## Definition Of Done

Sprint 1 is complete when:

- The product is framed as AI-assisted verification control plane.
- The LLM boundary is explicit.
- The harness authority is explicit.
- Operational knobs are documented.
- Non-negotiable safety policies are documented.
- Downstream simulator and verification runner have a stable input contract.

## Handoff

Sprint 2 consumes the typed plan and builds the first local simulator.

Sprint 4 later expands the simulator into:

```text
ScenarioSpec -> ScenarioMatrix -> VerificationRunner -> RiskReport
```
