# SwarmForge Harness

**Schema-first, simulator-verified LLM control plane for safe OTA tuning across virtual edge swarms.**

SwarmForge Harness is a hackathon-grade technical demo for using the OpenAI API to transform a natural-language engineering request into a safe, validated, canary-deployed OTA tuning plan for a fleet of virtual IoT/embedded devices.

The core idea is not "LLM writes code and ships it." The core idea is a modern LLM harness:

```text
Engineer prompt
  -> LLM intent extraction
  -> schema-constrained optimization plan
  -> safety validation
  -> local simulation
  -> metric scoring
  -> canary deployment
  -> telemetry monitoring
  -> rollback decision
  -> trace/eval record
```

The LLM proposes. The harness decides.

## Problem

Edge fleets often need fast configuration changes while operating in noisy, bandwidth-constrained environments. For example, a swarm of off-road racing sensors may start with aggressive telemetry settings:

- 10 Hz sample rate
- noisy accelerometer stream
- verbose logging
- high network bandwidth
- high battery drain

An embedded engineer may know what they want:

> The vehicle is entering a muddy terrain zone with heavy vibration. Smooth the acceleration signal with a median filter, reduce sampling to 2 Hz, and move logs to warning level.

But converting that request into a fleet-safe OTA change requires several non-trivial steps:

- translate intent into machine-valid configuration
- prevent unsafe generated code or invalid parameters
- estimate effect before deployment
- avoid full-fleet blast radius
- detect telemetry regressions
- roll back automatically
- keep a trace of why the system made each decision

SwarmForge Harness is the control plane for that loop.

## Core Thesis

LLMs are powerful at interpreting operator intent, but direct deployment is unsafe. A credible engineering system needs:

- **Structured outputs** so the model returns a constrained object, not arbitrary text.
- **Tool/function boundaries** so side effects are owned by the application, not the model.
- **Simulation before deployment** so candidate plans are tested against virtual sensor streams.
- **Canary rollout** so the first deployment touches only a small percentage of nodes.
- **Guardrails and rollback** so failure is visible, bounded, and recoverable.
- **Tracing and evals** so the harness can be inspected and improved over time.

This makes the project stronger than a typical "chatbot for IoT" demo. It demonstrates an AI control plane with production-minded safety mechanics.

## Proposed Tech Stack

### LLM Harness

- **OpenAI Responses API** as the main model interface.
- **Structured Outputs** for strict JSON schema adherence.
- **Function calling / tool calling** for harness-owned operations:
  - `validate_plan`
  - `simulate_plan`
  - `score_candidate`
  - `prepare_canary`
  - `dispatch_ota`
  - `rollback_nodes`
- **Model target:** use the latest available high-capability OpenAI model for reasoning/coding tasks; keep a smaller fallback model for fast/cheap iteration.
- **OpenAI tracing/eval concepts** as the design reference for observability and quality loops.

### Backend

- **Python 3.12**
- **FastAPI**
- **Pydantic** for schemas and validation
- **OpenAI Python SDK**
- **asyncio** for background telemetry and harness jobs
- **paho-mqtt** or an async MQTT client for broker communication

### Edge Swarm Simulation

- **Python edge agents** running as lightweight containers
- Each node simulates:
  - accelerometer noise
  - temperature
  - battery drain
  - network payload rate
  - current OTA configuration
- Hot-swap behavior is simulated by updating runtime filter/config state without restarting the node process.

### Messaging

- **Eclipse Mosquitto MQTT broker**
- Topic layout:

```text
swarm/control/ota
swarm/node/{node_id}/ota
swarm/telemetry/{node_id}
swarm/events/{node_id}
```

### Dashboard

MVP dashboard should be custom and lightweight instead of starting with Grafana.

- **HTML/CSS/TypeScript or React**
- **WebSocket** connection to FastAPI
- Real-time panels:
  - active nodes
  - sample rate
  - telemetry volume
  - noise score
  - canary status
  - rollback events
  - latest LLM plan

Grafana + InfluxDB can be a stretch goal after the custom dashboard is working.

### Runtime

- **Docker Compose**
- Services:
  - `api`
  - `mqtt`
  - `edge-node` scaled N times
  - `web`

## Planned Repository Structure

The project should be built in small, separable modules:

```text
backend/
  app/
    main.py
    schemas.py
    llm_harness.py
    simulator.py
    mqtt_dispatcher.py
    telemetry_store.py
    rollback.py
edge-node/
  edge_agent.py
web/
  index.html
  styles.css
  app.js
docs/
  implementation-steps.md
docker-compose.yml
.env.example
```

The first implementation should keep these modules thin. The value is in the end-to-end harness loop, not in building a large framework too early.

## Harness Architecture

### 1. Intent Parser

Input:

```text
Xe đang vào vùng bùn lầy, rung lắc mạnh. Hãy giảm sample rate xuống 2Hz,
thêm median filter cho gia tốc, và chuyển log level sang WARNING.
```

Output should be a structured optimization request:

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
    "percentage": 5
  }
}
```

The model is not allowed to call deployment functions directly. It can only produce a candidate plan or request tool execution through approved tool schemas.

### 2. Schema Gate

The first safety boundary is structural.

The candidate plan must satisfy:

- valid JSON shape
- allowed filter types
- bounded sample rate range
- bounded filter window size
- valid log level
- canary required before full rollout
- rollback policy required for risky changes

Example constraints:

```text
sampling_rate_hz: 1..20
filter.type: none | moving_average | median | low_pass
filter.window_size: 1..15
deployment.strategy: canary | shadow | full_after_canary
deployment.percentage: 1..20 for first rollout
```

### 3. Static Safety Gate

For MVP, the preferred path is config/DSL only. This avoids arbitrary code execution.

If experimental generated Python filters are allowed later, they must pass static checks:

- no imports
- no file system access
- no network access
- no subprocess access
- no `eval`
- no unrestricted `exec`
- no infinite loop patterns where detectable
- only a small allowlist of math/list/statistics operations

The safer design is:

```text
LLM emits filter spec -> backend maps spec to trusted implementation
```

instead of:

```text
LLM emits arbitrary Python -> backend executes it
```

### 4. Simulator-in-the-Loop

Before deployment, the backend runs the candidate plan against a local simulated sensor stream.

Simulation should estimate:

- signal smoothness improvement
- expected telemetry messages per second
- bandwidth reduction
- CPU cost approximation
- whether output contains invalid values
- whether latency exceeds acceptable threshold

The harness can reject a plan even if the JSON is valid.

Example rejection:

```json
{
  "status": "rejected",
  "reason": "Median window size 15 reduced noise but introduced too much latency for racing telemetry."
}
```

### 5. Candidate Scoring

Each plan gets a score before deployment.

Suggested scoring dimensions:

```text
score = noise_reduction_gain
      + bandwidth_reduction_gain
      - latency_penalty
      - battery_penalty
      - safety_risk_penalty
```

The score is not only for ranking. It helps explain to judges why the harness accepted one plan and rejected another.

### 6. Canary Deployment

The first OTA dispatch targets only a subset of nodes.

Example:

```text
Fleet size: 50 nodes
Canary percentage: 5%
Canary nodes: 3 nodes
Observation window: 5-10 seconds
Success conditions:
  - telemetry still arriving
  - exception rate below threshold
  - sample rate converges near target
  - noise score improves
```

Only after canary success can the harness promote the plan to a wider rollout.

### 7. Telemetry Monitor

The monitor subscribes to MQTT telemetry and maintains short rolling windows:

- messages per second per node
- latest sensor value
- smoothed sensor value
- exception count
- active config version
- battery estimate
- bandwidth estimate

The dashboard reads these windows through WebSocket.

### 8. Auto-Rollback

Rollback should trigger when:

- canary nodes stop sending telemetry
- node exception rate spikes
- sensor output becomes NaN/invalid
- actual sample rate deviates too far from target
- latency crosses threshold

Rollback sends the last known stable config back to affected nodes.

Rollback is one of the strongest demo moments because it proves the system does not blindly trust AI-generated changes.

### 9. Trace and Eval Record

Every optimization run should produce a durable record:

```json
{
  "run_id": "run_2026_06_27_001",
  "prompt": "...",
  "model_plan": {},
  "schema_result": "passed",
  "simulation_result": {},
  "score": 0.87,
  "deployment": "canary",
  "canary_result": "passed",
  "final_action": "promoted",
  "rollback": false
}
```

This record is useful for:

- debugging
- demo replay
- offline eval datasets
- comparing prompts and model versions
- proving harness decisions are auditable

## API Surface Draft

### `POST /optimize`

Accepts an engineer prompt and starts a harness run.

Request:

```json
{
  "prompt": "Reduce telemetry bandwidth and smooth accelerometer noise.",
  "mode": "safe"
}
```

Response:

```json
{
  "run_id": "run_001",
  "status": "running"
}
```

### `GET /runs/{run_id}`

Returns the current state of a harness run.

### `POST /runs/{run_id}/approve`

Optional human approval gate before OTA dispatch.

### `POST /runs/{run_id}/rollback`

Manual rollback endpoint.

### `WS /telemetry`

Streams dashboard state.

## Demo Script

### Minute 1: Baseline Swarm

Show the dashboard with 50 virtual nodes sending noisy telemetry at 10 Hz.

Explain:

> The fleet is over-sampling in harsh terrain. Bandwidth is high, the signal is noisy, and battery drain is increasing.

### Minute 2: Chat-to-Harness

Enter:

```text
Xe đang đi vào vùng bùn lầy, rung lắc mạnh. Hãy triển khai median filter
để làm mượt tín hiệu gia tốc, giảm sample rate xuống 2Hz, và chuyển log
level sang WARNING.
```

Show the harness timeline:

```text
Prompt parsed
Structured plan generated
Schema validation passed
Simulation passed
Canary selected
OTA dispatched
Telemetry monitored
Plan promoted
```

### Minute 3: Real-Time Impact

Dashboard should visibly show:

- sample rate dropping from 10 Hz to around 2 Hz
- bandwidth decreasing
- acceleration signal becoming smoother
- canary progressing to full rollout
- trace record for the run

Then enter a risky request:

```text
Deploy an aggressive unstable filter to all nodes immediately.
```

Expected result:

```text
Harness blocks full rollout and forces canary.
```

Or:

```text
Canary fails, rollback triggered.
```

## Why This Is a Strong Hackathon Project

This project combines four strong technical signals:

1. **LLM application depth**: structured outputs, tools, guardrails, traces, eval-oriented records.
2. **Distributed systems**: MQTT broker, virtual swarm, rolling telemetry windows.
3. **Embedded/IoT realism**: OTA tuning, sampling rates, filters, noisy sensors, battery/bandwidth tradeoffs.
4. **Safety story**: simulation, canary, rollback, audit logs.

The highest-value message to judges:

> We are not using AI as an unchecked code generator. We are building a harness that turns AI intent into safe, measurable, reversible fleet actions.

## MVP Scope

The MVP should include:

- FastAPI backend
- OpenAI Responses API integration
- schema-constrained optimization plan
- local simulator
- MQTT broker
- 10-50 virtual edge nodes
- custom real-time dashboard
- canary deployment
- rollback path
- run trace records

## Stretch Scope

After MVP:

- generated Python filter mode with AST validator
- Grafana + InfluxDB
- multiple candidate generation and ranking
- shadow deployment mode
- offline eval dataset
- replayable demo runs
- multi-agent split between planner, validator, and deployment reviewer

## OpenAI Documentation References

- OpenAI Platform docs: https://platform.openai.com/docs
- Responses API guide: https://platform.openai.com/docs/guides/responses
- Structured Outputs guide: https://platform.openai.com/docs/guides/structured-outputs
- Function calling guide: https://platform.openai.com/docs/guides/function-calling
- OpenAI Agents SDK docs: https://openai.github.io/openai-agents-python/
- Agents SDK guardrails: https://openai.github.io/openai-agents-python/guardrails/
- Agents SDK tracing: https://openai.github.io/openai-agents-python/tracing/
- OpenAI Evals guide: https://platform.openai.com/docs/guides/evals
