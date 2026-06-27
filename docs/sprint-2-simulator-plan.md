# Sprint 2: Local Simulator And Baseline Metric Scoring

Sprint 2 builds the first deterministic simulator. It proves that a schema-valid plan can still be measured and rejected before deployment.

Sprint 2 is not the final verification story. It is the engine that Sprint 4 will run many times across an adversarial scenario matrix.

## Sprint Goal

Build a local simulator that can answer:

- Does the proposed filter reduce accelerometer noise?
- Does the sample-rate change reduce bandwidth?
- Does telemetry collection stay inside payload limits?
- Does the filter add too much latency?
- Should the plan be accepted or rejected for this one baseline scenario?

## Inputs

### `OptimizationPlan`

The simulator consumes the typed plan from Sprint 1.

### Baseline Config

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

The simulator generates deterministic accelerometer data:

```text
duration_seconds: 30
baseline_sample_rate_hz: 10
base_motion: smooth low-frequency wave
normal_noise: low jitter
terrain_event: high-vibration window
seed: fixed for replay
```

## Outputs

`SimulationResult`:

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

## Metrics

Noise score:

```text
noise_score = mean(abs(value[i] - value[i - 1]))
```

Bandwidth estimate:

```text
payload_per_sample_bytes =
  base_overhead_bytes
  + bytes_per_metric * collected_metric_count

bandwidth_kbps =
  sampling_rate_hz * payload_per_sample_bytes * 8 / 1000 * publish_mode_multiplier
```

Latency estimate:

```text
latency_penalty_ms = ((filter.window_size - 1) / 2) / baseline_sample_rate_hz * 1000
```

Score:

```text
score =
  noise_reduction_ratio * intent_weight
  + bandwidth_reduction_ratio * intent_weight
  + latency_budget_remaining * weight
  + payload_budget_remaining * weight
```

The current implementation uses intent-aware weights so bandwidth-only requests can pass without needing noise improvement.

## Acceptance Policy

Accept when all relevant intent checks pass:

- noise-focused plans reduce noise
- bandwidth-focused plans reduce bandwidth
- latency stays under rollback budget
- payload stays under telemetry cap
- score is above threshold

Reject when:

- latency exceeds budget
- payload exceeds cap
- noise gets worse for a noise request
- bandwidth gets worse for a bandwidth request
- score is too low

## Test Scenarios

| Scenario | Plan | Expected Result |
| --- | --- | --- |
| Happy path | `2Hz`, `median`, window `5`, summary telemetry | Accepted |
| Oversized filter | `2Hz`, `median`, window `15` | Rejected for latency |
| Payload too high | `10Hz`, raw all metrics, payload cap `1kbps` | Rejected for payload |
| No useful change | `10Hz`, no filter, raw telemetry | Rejected |
| Bandwidth only | `2Hz`, no filter, summary telemetry | Accepted |

## Current Code

Implemented modules:

```text
swarmforge/schemas.py
swarmforge/simulator.py
tests/test_simulator.py
```

Run:

```text
.venv/bin/python -m unittest
```

## Definition Of Done

Sprint 2 is complete when:

- deterministic local simulation runs without OpenAI
- happy-path median plan is accepted
- unsafe plans are rejected with reasons
- output is JSON-serializable
- tests are fast and local

## Sprint 4 Handoff

Sprint 4 should generalize this simulator:

```text
single baseline simulation
  -> many ScenarioSpec variants
  -> many SimulationResult records
  -> aggregate RiskReport
```

The simulator remains harness-owned. The model cannot override simulator failures.
