# Sprint 2: Local Simulator and Metric Scoring

Sprint 2 proves that SwarmForge Harness does not trust a valid-looking LLM plan blindly. A candidate `OptimizationPlan` must be tested against a local synthetic signal and scored before any OTA path is allowed.

The Sprint 2 thesis:

```text
Schema-valid does not mean deployment-safe.
The simulator must measure impact before canary.
```

## Sprint Goal

Build a local simulator contract that can answer:

- Does the proposed filter reduce accelerometer noise?
- Does the sample-rate change reduce telemetry bandwidth?
- Does the telemetry collection config stay within payload limits?
- Does the filter introduce too much latency?
- Should the harness accept, reject, or ask for a safer plan?

Sprint 2 should remain local. It does not require OpenAI, MQTT, Docker, edge nodes, or a dashboard.

## Inputs

### `OptimizationPlan`

The simulator consumes the approved Sprint 1 object:

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
  }
}
```

### Baseline Fleet Config

```json
{
  "sampling_rate_hz": 10,
  "log_level": "INFO",
  "filter": {
    "type": "none",
    "window_size": 1
  },
  "telemetry_collection": {
    "metrics": ["accelerometer", "temperature", "battery", "bandwidth"],
    "aggregation_window_seconds": 1,
    "publish_mode": "raw",
    "max_payload_kbps": 32
  }
}
```

### Synthetic Signal

The first simulator should generate a deterministic accelerometer stream:

```text
duration_seconds: 30
baseline_sample_rate_hz: 10
base_motion: smooth low-frequency wave
noise: random jitter
terrain_event: high-vibration window
seed: fixed for repeatable demos
```

The deterministic seed matters because judges should see repeatable before/after metrics.

## Outputs

The simulator returns a `SimulationResult`.

```json
{
  "accepted": true,
  "reason": "Noise and bandwidth improved within latency and payload limits.",
  "noise_score_before": 0.82,
  "noise_score_after": 0.41,
  "noise_reduction_ratio": 0.5,
  "bandwidth_before_kbps": 32.0,
  "bandwidth_after_kbps": 6.4,
  "bandwidth_reduction_ratio": 0.8,
  "latency_penalty_ms": 200,
  "payload_limit_kbps": 8,
  "estimated_payload_kbps": 6.4,
  "score": 0.87
}
```

Rejected example:

```json
{
  "accepted": false,
  "reason": "Median window size 15 reduced noise but exceeded the latency budget.",
  "noise_score_before": 0.82,
  "noise_score_after": 0.32,
  "noise_reduction_ratio": 0.61,
  "bandwidth_before_kbps": 32.0,
  "bandwidth_after_kbps": 6.4,
  "bandwidth_reduction_ratio": 0.8,
  "latency_penalty_ms": 700,
  "payload_limit_kbps": 8,
  "estimated_payload_kbps": 6.4,
  "score": 0.38
}
```

## Metrics

### Noise Score

Noise score should estimate short-term jitter in the accelerometer stream.

Recommended first implementation:

```text
noise_score = mean(abs(value[i] - value[i - 1]))
```

This is simple, explainable, and enough for the demo. Later versions can use variance, spectral energy, or domain-specific vibration features.

### Bandwidth Estimate

Recommended first implementation:

```text
payload_per_sample_bytes =
  base_overhead_bytes
  + bytes_per_metric * number_of_collected_metrics

bandwidth_kbps =
  sampling_rate_hz * payload_per_sample_bytes * 8 / 1000
```

Suggested constants:

```text
base_overhead_bytes: 32
bytes_per_metric: 16
```

`publish_mode` can apply a multiplier:

```text
raw: 1.0
summary: 0.45
summary_and_anomalies: 0.55
anomalies_only: 0.25
```

### Latency Penalty

Recommended first implementation:

```text
latency_penalty_ms = ((filter.window_size - 1) / 2) / baseline_sample_rate_hz * 1000
```

For `filter.type = none`, latency should be `0`.

### Score

The score should be explainable:

```text
score =
  noise_reduction_ratio * 0.45
  + bandwidth_reduction_ratio * 0.35
  + latency_budget_remaining * 0.15
  + payload_budget_remaining * 0.05
```

Where:

```text
latency_budget_remaining = 1 - min(latency_penalty_ms / rollback.max_latency_ms, 1)
payload_budget_remaining = 1 - min(estimated_payload_kbps / max_payload_kbps, 1)
```

Clamp score to `0..1`.

## Acceptance Policy

Accept a plan when all are true:

- `noise_score_after` is lower than `noise_score_before` for noise-focused intents.
- `bandwidth_after_kbps` is lower than `bandwidth_before_kbps` for bandwidth-focused intents.
- `latency_penalty_ms <= rollback.max_latency_ms`.
- `estimated_payload_kbps <= telemetry_collection.max_payload_kbps`.
- `score >= 0.6`.

Reject a plan when any are true:

- Filter produces invalid values.
- Latency exceeds the rollback budget.
- Estimated payload exceeds the plan payload limit.
- Noise gets worse for a noise-focused request.
- Bandwidth gets worse for a bandwidth-focused request.
- Score is below threshold.

## Test Scenarios

| Scenario | Plan | Expected Result |
| --- | --- | --- |
| Happy path | `2Hz`, `median`, window `5`, summary telemetry | Accepted |
| Oversized filter | `2Hz`, `median`, window `15` | Rejected for latency |
| Payload too high | `10Hz`, raw all metrics, payload cap `4kbps` | Rejected for payload |
| No useful change | `10Hz`, no filter, raw telemetry | Rejected for weak score |
| Bandwidth only | `2Hz`, no filter, summary telemetry | Accepted if intent is bandwidth-focused |

## Sprint 2 Backlog

| Item | Requirement | Output |
| --- | --- | --- |
| Simulator contract | Define input/output shapes | This document |
| Synthetic signal | Deterministic noisy accelerometer stream | Repeatable sample data |
| Filter simulation | Apply trusted filter specs only | `none`, `moving_average`, `median`, `low_pass` |
| Telemetry estimate | Estimate payload and bandwidth | `bandwidth_before/after` |
| Latency estimate | Estimate filter delay | `latency_penalty_ms` |
| Scoring | Combine gains and penalties | `score` |
| Acceptance cases | Verify happy and rejection paths | Scenario outputs |

## Local Test Command

After implementation starts, the local simulator tests should run with:

```text
.venv/bin/python -m unittest
```

## Definition of Done

Sprint 2 is complete when:

- A deterministic local simulation can run without OpenAI, MQTT, Docker, or edge nodes.
- The happy-path median filter plan is accepted.
- Oversized filters are rejected for latency.
- Excess telemetry payload is rejected.
- The simulator returns a clear `SimulationResult`.
- The output can be used by Sprint 3 before any OpenAI API integration.

## Sprint 3 Handoff

Sprint 3 should call the OpenAI Responses API to produce `OptimizationPlan`, then immediately pass that plan into:

```text
schema validation -> simulator -> deployment decision
```

The simulator remains harness-owned. The model may suggest a plan, but it cannot override simulator rejection.
