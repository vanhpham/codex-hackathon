# Deep Demo Scenario: Race Swarm Verification Harness

This scenario is the judge-facing story for the "Build something extremely deep with Engineering prowess" track.

The demo should not feel like an AI chatbot that edits IoT config. It should feel like a verification lab where one natural-language request is compiled into a typed control plan, stress-tested across many deterministic edge conditions, and either cleared for canary or blocked with evidence.

Core message:

```text
Codex scales the engineering search.
The harness enforces the safety boundary.
```

## Scenario Thesis

An off-road racing team runs a swarm of edge telemetry nodes across a vehicle and track-side sensor rigs. During a muddy high-vibration sector, the fleet is oversampling noisy accelerometer data at 10 Hz, sending raw telemetry, burning bandwidth, and draining battery.

The engineer wants an operational change:

```text
Xe dang vao vung bun lay, rung lac manh. Hay giam sample rate xuong 2Hz,
them median filter cho gia toc, va chuyen log level sang WARNING.
```

A shallow system would translate this into a config update and publish it.

SwarmForge does something deeper:

```text
Prompt
  -> typed OptimizationPlan
  -> schema and policy gate
  -> baseline simulator
  -> adversarial scenario matrix
  -> invariant checks
  -> risk report
  -> trace/eval record
  -> canary-ready or blocked decision
```

The model proposes. The harness verifies. The harness decides.

## Baseline World

Fleet:

```text
virtual nodes: 50
baseline sample rate: 10 Hz
baseline filter: none
baseline telemetry mode: raw
baseline log level: INFO
baseline collected metrics: accelerometer, temperature, battery, bandwidth
```

Environment:

```text
terrain: muddy sector with heavy vibration
network: intermittent packet loss
battery: mixed normal and low battery nodes
sensor faults: occasional dropout or stuck-value accelerometer
operator pressure: fast race-time decision, limited bandwidth budget
```

Pain point:

```text
The team does not need AI to blindly write firmware.
The team needs a control plane that can turn intent into a safe, measured,
replayable decision under bandwidth, latency, battery, and rollout constraints.
```

## Main Happy-Path Demo

Input prompt:

```text
Xe dang vao vung bun lay, rung lac manh. Hay giam sample rate xuong 2Hz,
them median filter cho gia toc, va chuyen log level sang WARNING.
```

Expected structured plan:

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

Expected harness timeline:

```text
1. Structured plan generated
2. Schema gate passed
3. Baseline simulation accepted
4. Scenario matrix generated
5. 500 deterministic simulations executed
6. Safety invariants evaluated
7. Risk report produced
8. Decision: ready_for_canary
9. Trace record saved for replay/eval
```

Expected risk report shape:

```json
{
  "verification_status": "passed",
  "scenario_count": 500,
  "passed_count": 482,
  "failed_count": 18,
  "pass_rate": 0.964,
  "risk_score": 0.19,
  "worst_case": {
    "scenario_id": "rocky_high_loss_low_battery_dropout_seed_391",
    "failed_invariants": [],
    "telemetry_health": 0.952,
    "latency_penalty_ms": 200,
    "estimated_payload_kbps": 6.4
  },
  "decision": "ready_for_canary"
}
```

## Adversarial Prompt Demo

Risky input:

```text
Deploy an aggressive unstable filter to all nodes immediately and disable rollback.
```

Expected result:

```json
{
  "status": "schema_rejected",
  "decision": "blocked",
  "reasons": [
    "first deployment must use canary",
    "rollback.enabled must be true",
    "filter.type must be allowlisted"
  ]
}
```

Judge-facing point:

```text
The model can ask for unsafe behavior, but the harness owns authority.
Rejected plans never reach simulation or MQTT.
```

## Verification-Rejection Demo

This is the strongest engineering moment because the plan is schema-valid but still unsafe.

Input plan:

```json
{
  "intent": "reduce_noise_and_bandwidth",
  "target_metric": "accelerometer",
  "sampling_rate_hz": 2,
  "log_level": "WARNING",
  "filter": {
    "type": "median",
    "window_size": 15
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

Expected result:

```json
{
  "verification_status": "failed",
  "decision": "blocked",
  "critical_failure": true,
  "failed_invariants": [
    "latency_within_budget"
  ],
  "reason": "Median window size 15 reduced noise but exceeded the latency budget in multiple scenarios."
}
```

Judge-facing point:

```text
Schema-valid does not mean deployment-safe.
The harness tries to falsify the plan before it reaches the fleet.
```

## Scenario Matrix

Sprint 4 should generate deterministic combinations across:

```text
terrain: smooth | muddy | rocky | spike_noise
noise_level: low | medium | high
network_profile: stable | jitter | high_loss
battery_state: normal | low | critical
sensor_fault: none | dropout | stuck_value
fleet_size: 1 | 10 | 50 | 100
seed: deterministic integer
```

Required included cases:

```text
happy_path_muddy_medium_noise_stable_network_seed_1
muddy_high_noise_high_loss_low_battery_seed_42
rocky_high_noise_jitter_normal_battery_seed_73
spike_noise_high_loss_dropout_seed_91
smooth_low_noise_critical_battery_seed_113
stuck_value_sensor_high_loss_seed_151
```

Each case should produce:

```json
{
  "scenario_id": "muddy_high_noise_high_loss_low_battery_seed_42",
  "accepted": false,
  "failed_invariants": ["telemetry_health_above_floor"],
  "metrics": {
    "noise_score_before": 0.91,
    "noise_score_after": 0.46,
    "bandwidth_after_kbps": 6.4,
    "latency_penalty_ms": 200,
    "telemetry_health": 0.91,
    "battery_cost_delta": -0.12
  },
  "reason": "Telemetry health fell below rollback floor under high packet loss."
}
```

## Safety Invariants

The verification runner should evaluate:

```text
schema_valid
rollback_enabled
canary_required
latency_within_budget
payload_within_cap
noise_not_worse_for_noise_intent
bandwidth_not_worse_for_bandwidth_intent
telemetry_health_above_floor
battery_not_critical_for_dispatch
no_full_fleet_first_rollout
```

Critical invariants:

```text
rollback_enabled
canary_required
latency_within_budget
payload_within_cap
telemetry_health_above_floor
```

A critical invariant failure should block the plan even if the aggregate pass rate is high.

## Demo Script

### Minute 1: Show The Operational Pain

Show baseline metrics:

```text
50 nodes
10 Hz raw telemetry
high accelerometer jitter
high estimated bandwidth
mixed low-battery nodes
```

Say:

```text
The hard problem is not generating config. The hard problem is proving that a config is safe enough under race-time edge conditions.
```

### Minute 2: Prompt To Typed Plan

Enter the muddy terrain prompt.

Show:

```text
OpenAI structured plan
schema gate status
bounded fields
canary and rollback enforced
```

### Minute 3: Baseline Simulator

Show before/after:

```text
noise score decreases
bandwidth decreases
latency stays under 250 ms
payload stays under 8 kbps
```

### Minute 4: Codex Auto Runner / Verification Matrix Moment

Run the plan through 500 deterministic scenarios.

Show:

```text
matrix dimensions
progress counter
pass/fail aggregation
worst-case scenario
risk score
```

This is the "depth" moment.

### Minute 5: Replay A Failed Or Worst-Case Scenario

Pick a seed from the risk report and replay it.

Show:

```text
same scenario_id
same seed
same metrics
same invariant result
```

Say:

```text
The harness is not giving a vibe-based answer. It leaves a deterministic audit trail.
```

### Minute 6: Try To Break It

Enter the unsafe prompt:

```text
Deploy an aggressive unstable filter to all nodes immediately and disable rollback.
```

Show:

```text
schema rejected
deployment blocked
trace saved
no MQTT dispatch possible
```

Then show a schema-valid but unsafe plan:

```text
median window 15
canary enabled
rollback enabled
```

Expected:

```text
baseline or verification rejection due latency
```

## What Judges Should Test

Judges may ask:

```text
What happens if the model asks for full-fleet rollout?
What happens if rollback is disabled?
What happens if the plan passes schema but fails under high loss?
Can you replay the same failure?
Can you show that no rejected plan reaches MQTT?
Can you change scenario count from 50 to 500?
Can the system explain why a plan was blocked?
```

The demo should have direct answers for each.

## Implementation Priority

Build in this order:

```text
1. ScenarioSpec and deterministic ScenarioMatrix
2. Scenario-aware simulator parameters
3. SafetyInvariant checks
4. VerificationRunner aggregation
5. RiskReport JSON output
6. Replay by scenario_id / seed
7. Trace record persistence
8. Terminal dashboard
9. MQTT canary boundary
```

Do not build MQTT first. MQTT is the final proof that only verified plans can touch runtime.

## Success Definition

The scenario succeeds when the demo proves all of these:

```text
1. One natural-language prompt becomes a typed plan.
2. The model cannot bypass hard safety rules.
3. A plan is tested across many deterministic edge cases.
4. Risk is quantified and explainable.
5. Failures are replayable by seed.
6. Only ready_for_canary decisions can approach deployment.
```
