# Sprint 4: Scalable Verification Runner

Sprint 4 is the core pivot for the hackathon track. It turns one baseline-accepted plan into a large deterministic verification matrix and a risk report.

The Sprint 4 thesis:

```text
One LLM plan is not enough.
The harness must try to falsify it across many edge-swarm conditions.
```

## Sprint Goal

Build:

```text
OptimizationPlan
  -> ScenarioMatrix
  -> VerificationRunner
  -> SafetyInvariant checks
  -> RiskReport
  -> ready_for_canary or blocked
```

This is the most important engineering-depth sprint.

## Core Models

### `ScenarioSpec`

Represents one deterministic edge condition:

```json
{
  "scenario_id": "muddy_high_loss_low_battery_seed_42",
  "seed": 42,
  "duration_seconds": 30,
  "baseline_sample_rate_hz": 10,
  "terrain": "muddy",
  "noise_level": "high",
  "network_profile": "high_loss",
  "battery_state": "low",
  "sensor_fault": "none",
  "fleet_size": 50
}
```

Recommended dimensions:

```text
terrain: smooth | muddy | rocky | spike_noise
noise_level: low | medium | high
network_profile: stable | jitter | high_loss
battery_state: normal | low | critical
sensor_fault: none | dropout | stuck_value
fleet_size: 1 | 10 | 50 | 100
seed: deterministic integer
```

### `SafetyInvariant`

Each invariant checks a result:

```text
latency_within_budget
payload_within_cap
noise_not_worse
bandwidth_not_worse
telemetry_health_above_floor
rollback_enabled
canary_required
```

### `VerificationCaseResult`

```json
{
  "scenario_id": "muddy_high_loss_low_battery_seed_42",
  "accepted": false,
  "failed_invariants": ["telemetry_health_above_floor"],
  "metrics": {
    "noise_score_after": 0.62,
    "bandwidth_after_kbps": 7.1,
    "latency_penalty_ms": 200,
    "telemetry_health": 0.74
  },
  "reason": "Telemetry health fell below rollback floor under high packet loss."
}
```

### `RiskReport`

```json
{
  "verification_status": "passed",
  "scenario_count": 500,
  "passed_count": 481,
  "failed_count": 19,
  "pass_rate": 0.962,
  "risk_score": 0.18,
  "worst_case": {
    "scenario_id": "network_jitter_high_loss_seed_91",
    "telemetry_health": 0.83
  },
  "failed_scenarios": [
    "network_jitter_high_loss_seed_91"
  ],
  "decision": "ready_for_canary"
}
```

## Scenario Matrix Generation

The first implementation can generate a deterministic subset:

```text
base scenario count: 50
expanded scenario count: 100-500
seed range: 1..N
```

Generation rules:

- always include the happy-path muddy terrain scenario
- always include at least one network stress case
- always include at least one battery-low case
- always include at least one sensor-dropout case
- keep matrix deterministic for replay

## Acceptance Policy

Pass when:

```text
pass_rate >= 0.95
risk_score <= 0.25
no critical invariant failed
rollback remains enabled
canary remains required
```

Block when:

```text
pass_rate < 0.95
risk_score > 0.25
any critical invariant fails
telemetry health falls below minimum
latency exceeds budget in worst-case scenario
```

## CLI Requirement

Add:

```text
scripts/run_verification_matrix.py
```

Expected behavior:

```text
load prompt or sample plan
run OpenAI harness or fake plan
generate scenario matrix
run verification
print JSON risk report
```

## Test Scenarios

| Scenario | Expected Result |
| --- | --- |
| Good plan over 50 scenarios | `ready_for_canary` |
| Oversized filter over matrix | `blocked` |
| High-loss network case | failed scenario recorded |
| Deterministic seed replay | same report twice |
| Critical invariant failure | blocked regardless of pass rate |

## Definition Of Done

Sprint 4 is complete when:

- scenario matrix generation is deterministic
- verification runs many local simulations quickly
- invariant failures include actionable reasons
- risk report is JSON-serializable
- good plan passes
- risky plan is blocked
- tests cover deterministic replay and aggregation

## Handoff

Sprint 5 consumes `RiskReport` and persists it as trace/eval data.

