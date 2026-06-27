# SwarmForge Harness Implementation Steps

This document breaks the system into small build phases. The goal is to keep the project demoable at every stage.

## Five-Sprint Delivery Map

The detailed phases below can be grouped into five hackathon-friendly sprints:

```text
Sprint 1: Product contract + schema gate
Sprint 2: Local simulator + metric scoring
Sprint 3: OpenAI structured harness
Sprint 4: MQTT edge loop + canary/rollback
Sprint 5: Dashboard + trace/eval polish
```

Sprint 1 is tracked in:

```text
docs/sprint-1-product-contract.md
```

Sprint 2 is tracked in:

```text
docs/sprint-2-simulator-plan.md
```

Sprint 3 is tracked in:

```text
docs/sprint-3-openai-harness.md
```

Sprint 4 is tracked in:

```text
docs/sprint-4-mqtt-edge-loop.md
```

## Phase 0: Product Decision

Decide the core promise:

```text
Natural-language engineering request -> safe OTA tuning plan -> simulated edge swarm impact
```

Decide the first demo scenario:

```text
Noisy off-road accelerometer stream
10 Hz baseline telemetry
LLM proposes 2 Hz median-filtered telemetry
Harness validates, simulates, canaries, promotes, or rolls back
```

## Phase 1: Repository Skeleton

Create:

```text
backend/
edge-node/
web/
docs/
docker-compose.yml
.env.example
```

Do not over-abstract early. Keep the first version easy to run and easy to explain.

## Phase 2: Schemas First

Define the optimization plan schema before implementing the OpenAI call.

Core models:

```text
OptimizationPlan
FilterSpec
DeploymentSpec
RollbackPolicy
SimulationResult
HarnessRun
TelemetrySnapshot
```

Important constraints:

```text
sampling_rate_hz between 1 and 20
filter.type from an allowlist
filter.window_size bounded
first deployment must be canary
rollback policy required
```

Acceptance:

```text
Backend can validate a hard-coded plan.
Invalid plans return clear rejection reasons.
```

## Phase 3: Simulator

Build the local simulator before real MQTT deployment.

Input:

```text
baseline synthetic signal
candidate OptimizationPlan
```

Output:

```text
noise_score_before
noise_score_after
bandwidth_before
bandwidth_after
latency_penalty
accepted / rejected
reason
```

Acceptance:

```text
Median filter reduces noise score.
Lower sample rate reduces estimated bandwidth.
Oversized filter window is rejected for latency.
```

## Phase 4: OpenAI Harness Call

Integrate OpenAI API only after schemas and simulator exist.

Recommended behavior:

```text
User prompt
  -> Responses API
  -> structured OptimizationPlan
  -> local schema validation
  -> simulation
```

Keep the model output limited to a plan. Do not deploy from inside the model response.

Acceptance:

```text
Prompt creates a valid plan.
Malformed or unsafe prompt gets corrected or rejected.
No OTA action happens until local gates pass.
```

## Phase 5: MQTT and Edge Nodes

Add Mosquitto and one edge node.

Node behavior:

```text
publish telemetry at configured sample rate
subscribe to OTA config topic
apply config without process restart
publish events on config applied / exception / rollback
```

Acceptance:

```text
One node sends telemetry.
Backend receives telemetry.
Backend can change sample rate through MQTT.
```

## Phase 6: Swarm Scaling

Scale edge nodes through Docker Compose.

Target:

```text
10 nodes first
50 nodes after stable
```

Acceptance:

```text
Dashboard/backend can show active node count.
Telemetry remains stable under load.
```

## Phase 7: Canary Deployment

Implement canary selection and observation window.

Flow:

```text
select small node subset
dispatch candidate config
monitor for 5-10 seconds
promote if healthy
rollback if unhealthy
```

Acceptance:

```text
Only canary nodes receive first update.
Healthy canary promotes to rest of fleet.
Unhealthy canary rolls back automatically.
```

## Phase 8: Dashboard

Build a custom dashboard first.

Panels:

```text
fleet status
current run timeline
sample rate chart
bandwidth estimate
noise score
canary status
rollback events
latest structured plan
```

Acceptance:

```text
User can run the 3-minute demo without looking at terminal logs.
```

## Phase 9: Eval Records

Persist every run as a JSON trace-like record.

Record:

```text
prompt
model plan
validation result
simulation result
deployment decision
canary outcome
rollback outcome
```

Acceptance:

```text
Past runs can be inspected and used as future eval cases.
```

## Phase 10: Polish and Stretch

Possible stretch work:

```text
Grafana + InfluxDB
AST-validated generated filter code
multi-candidate ranking
shadow deployment
offline eval dataset
demo replay button
```

Only add these after the MVP demo path is reliable.

## Recommended Build Order

```text
1. Schemas
2. Simulator
3. OpenAI structured plan
4. MQTT one-node loop
5. Swarm scale
6. Canary and rollback
7. Dashboard
8. Trace/eval records
```

This order keeps the riskiest logic visible early and avoids spending too much time on infrastructure before the harness is convincing.
