# SwarmForge Harness

**AI-assisted verification control plane for safe edge-swarm operational tuning.**

SwarmForge Harness is a hackathon project for the "Build something extremely deep with engineering prowess" track. It uses the OpenAI API to turn an engineer's natural-language intent into a typed control plan, then proves or rejects that plan through schema gates, adversarial scenario generation, multi-simulation verification, risk scoring, and auditable traces.

The project is not a chatbot and not "LLM writes code and deploys it." The core system is a verification harness:

```text
Engineer prompt
  -> OpenAI structured control plan
  -> schema and policy gate
  -> adversarial scenario matrix
  -> multi-simulation verification runner
  -> invariant checks and risk report
  -> canary-ready decision or blocked decision
  -> trace/eval record
```

The model proposes. The harness verifies. The harness decides.

## Why This Fits The Track

Judges for this track are expected to be strong engineers. A shallow "AI config app" would not be enough. SwarmForge is framed as an engineering verification system:

- **Typed control-plane IR:** Natural language becomes a constrained `OptimizationPlan`, not free-form instructions.
- **Harness-owned side effects:** The model cannot deploy, publish MQTT, disable rollback, or run arbitrary code.
- **Adversarial verification:** A single plan is tested against many deterministic edge-swarm scenarios.
- **Safety invariants:** The harness checks latency, bandwidth, telemetry health, rollback availability, rollout blast radius, and scenario pass rate.
- **Risk reporting:** The output is a measurable decision record, not a vague answer.
- **Replayability:** Scenario seeds and run traces make failures inspectable.

The "sneak move" is that the demo begins with a simple engineering prompt, but the system behind it performs a serious verification workflow.

## Product Thesis

Edge swarms need fast operational tuning, but direct LLM-to-deployment is unsafe. A credible AI control plane must separate suggestion from authority:

```text
LLM role: interpret intent and propose a typed plan.
Harness role: validate, stress test, score, block, or prepare for canary.
```

The key line:

```text
Codex scales the engineering search. The harness enforces safety.
```

## Demo Scenario

Baseline:

```text
Domain: off-road edge telemetry swarm
Signal: noisy accelerometer stream
Baseline sample rate: 10 Hz
Baseline filter: none
Baseline telemetry mode: raw
Problem: noisy signal, high bandwidth, high battery cost
```

Engineer prompt:

```text
Xe dang vao vung bun lay, rung lac manh. Hay giam sample rate xuong 2Hz,
them median filter cho gia toc, va chuyen log level sang WARNING.
```

Expected visible result:

```text
Structured plan generated
Schema gate passed
Scenario matrix generated
500 simulations executed
Safety invariants evaluated
Risk report produced
Decision: ready_for_canary
```

Risky prompt:

```text
Deploy an aggressive unstable filter to all nodes immediately and disable rollback.
```

Expected result:

```text
Decision: blocked
Reasons:
- first deployment must use canary
- rollback.enabled must be true
- unsafe rollout blast radius
```

## Control Knobs

The harness is not limited to a few config-manager fields. It supports a schema-controlled set of operational knobs:

| Area | Tunable Controls |
| --- | --- |
| Telemetry | sample rate, collected metrics, aggregation window, payload cap |
| Signal processing | filter type, filter window, low-pass settings |
| Power | power mode, duty cycle, sleep interval |
| Network | batching, compression, retry policy, MQTT QoS |
| Logging | log level, event sampling, error-only mode |
| Anomaly detection | threshold, debounce window, alert severity |
| Deployment | canary percentage, observation window, rollout ring |
| Rollback | latency cap, error-rate cap, telemetry-health floor |

The model can propose values for these knobs. The backend maps them to trusted implementations.

## Safety Model

Preferred MVP path:

```text
LLM emits typed control spec -> harness maps spec to trusted implementation
```

Avoid for MVP:

```text
LLM emits arbitrary Python -> backend executes it
```

If generated code mode is explored later, it must require AST validation, no imports unless allowlisted, no filesystem access, no subprocess access, no network access, no `eval`, no unrestricted `exec`, simulation before deployment, canary before rollout, and automatic rollback on health failure.

## Architecture

### 1. Structured Plan

OpenAI Responses API returns a strict `OptimizationPlan` through Structured Outputs.

The model may produce:

- intent
- target metric
- operational knob changes
- deployment request
- rollback policy
- rationale

The model may not:

- deploy directly
- publish MQTT messages
- call rollback directly
- run generated code
- bypass canary
- disable rollback

### 2. Schema And Policy Gate

The first safety gate checks hard constraints:

```text
sample rate: 1..20 Hz
filter type: none | moving_average | median | low_pass
filter window: 1..15
first rollout: canary only
rollback: required
telemetry payload cap: bounded
```

Rejected plans never reach simulation or deployment.

### 3. Scenario Matrix

The verification runner expands one candidate plan into many deterministic scenarios:

```text
terrain: smooth | muddy | rocky | spike_noise
battery: normal | low | critical
network: stable | jitter | high_loss
sensor: normal | dropout | stuck_value
fleet size: 1 | 10 | 50 | 100
seed: deterministic replay id
```

### 4. Multi-Simulation Verification

Each scenario runs the plan against a synthetic edge-swarm simulator. The runner records:

- noise before/after
- bandwidth before/after
- latency penalty
- payload estimate
- telemetry health
- battery cost estimate
- invariant failures

### 5. Risk Report

The harness aggregates results:

```json
{
  "verification_status": "passed",
  "scenario_count": 500,
  "pass_rate": 0.962,
  "risk_score": 0.18,
  "failed_scenarios": ["network_jitter_high_loss"],
  "decision": "ready_for_canary"
}
```

### 6. Canary Boundary

Only a `ready_for_canary` decision may become a deployment artifact. MQTT/edge-node rollout is intentionally downstream of verification.

## Current Code Status

For the latest branch/sprint audit, see:

```text
docs/current-state-audit.md
```

Implemented:

- `swarmforge/openai_contract.py`: Pydantic Structured Output model.
- `swarmforge/harness.py`: OpenAI plan call, schema validation, simulator call, final decision.
- `swarmforge/schemas.py`: internal dataclass validation and result models.
- `swarmforge/simulator.py`: deterministic signal simulation, filtering, bandwidth, latency, scoring.
- `swarmforge/scenarios.py`: deterministic adversarial scenario matrix.
- `swarmforge/invariants.py`: safety invariant checks.
- `swarmforge/verification.py`: multi-simulation verification runner.
- `swarmforge/risk.py`: risk report and per-case result models.
- `swarmforge/adaptive_verification.py`: LLM-aware counterexample generation with deterministic fallback.
- `swarmforge/setting_suggester.py`: suggestion report for safer next plan settings.
- `swarmforge/traces.py`: trace persistence, replay payload, and eval export.
- `swarmforge/ota.py`, `swarmforge/topics.py`, `swarmforge/edge_runtime.py`: trusted canary mapping and in-memory edge runtime.
- `scripts/run_openai_harness.py`: live OpenAI SDK smoke path.
- `scripts/run_verification_matrix.py`: local verification matrix smoke path with traces.
- `scripts/replay_trace_case.py`: replay one saved scenario deterministically.
- `scripts/export_eval_case.py`: export eval-style fixture from a saved trace.
- `scripts/run_canary_demo.py`: execute verification-safe canary run to in-memory nodes.
- unit tests for simulator, harness, scenarios, verification, trace replay, and canary runtime.

## Run Commands

Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Run unit tests:

```bash
.venv/bin/python -m unittest
```

Run live OpenAI structured harness:

```bash
.venv/bin/python scripts/run_openai_harness.py
```

Run local verification matrix:

```bash
.venv/bin/python scripts/run_verification_matrix.py --scenario-count 50
```

Run canary demo from a built-in ready payload:

```bash
.venv/bin/python scripts/run_canary_demo.py
```

Run canary demo from a saved trace:

```bash
.venv/bin/python scripts/run_canary_demo.py --trace traces/<run_id>.json --node-count 10
```

Sprint 6 runtime + Sprint 7 web dashboard (runtime visualization):

```bash
# start local Mosquitto broker
docker compose -f docker/docker-compose.yml up -d

# optional: run N MQTT edge-node agents (each one listens to OTA and publishes telemetry)
.venv/bin/python scripts/run_sprint6_nodes.py --node-count 8 --broker-host localhost

# run web dashboard + canary loop (embedded runtime nodes)
.venv/bin/python scripts/sprint7_web.py --broker-mode mqtt --node-count 8 --broker-host localhost --port 8080
```

If you prefer fully in-memory runtime (no Docker required), switch to:

```bash
.venv/bin/python scripts/sprint7_web.py --broker-mode in-memory --node-count 5
```

Backward-compatible command (kept for earlier writeups):

```bash
.venv/bin/python scripts/sprint6_web.py --broker-mode in-memory --node-count 5
```

Shut down broker when done:

```bash
docker compose -f docker/docker-compose.yml down
```

Run matrix + trace persistence + suggestion block:

```bash
.venv/bin/python scripts/run_verification_matrix.py \
  --scenario-count 50 \
  --adaptive \
  --adaptive-rounds 1 \
  --adaptive-budget 20 \
  --workers 4 \
  --suggest-settings \
  --trace-dir traces
```

Replay one recorded scenario from trace:

```bash
.venv/bin/python scripts/replay_trace_case.py traces/<run_id>.json --scenario-id <scenario_id>
```

Export eval fixture from trace:

```bash
.venv/bin/python scripts/export_eval_case.py traces/<run_id>.json --out eval_case.json
```

Run adaptive matrix + setting suggestions:

```bash
.venv/bin/python scripts/run_verification_matrix.py \
  --scenario-count 50 \
  --adaptive \
  --adaptive-rounds 1 \
  --adaptive-budget 20 \
  --workers 4 \
  --suggest-settings
```

Sample adaptive/suggestion output:

```json
{
  "verification": {
    "adaptive_cycles": 1,
    "candidate_scenarios": [
      "adaptive_muddy_high_loss_low_critical_dropout_seed_51"
    ],
    "adaptive_metadata": [
      {
        "cycle": 1,
        "generated_candidates": 2,
        "seed_range": [51, 71],
        "target_invariants": ["latency_within_budget"],
        "failed_in_cycle": 1,
        "passed_in_cycle": 1
      }
    ]
  },
  "setting_suggestions": {
    "reason": "Blocked run can improve by trying one option at a time, then re-running verification. Current risk=0.67, pass_rate=0.67.",
    "confidence": 0.9,
    "mutually_exclusive_options": [
      {
        "description": "Reduce canary blast radius to lower tail latency risk.",
        "changes": {
          "deployment": {
            "percentage": 4
          }
        }
      }
    ]
  }
}
```

Required local `.env`:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.5
```

Do not commit `.env`.

## Revised Sprint Roadmap

```text
Sprint 1: Product contract and typed control plan
Sprint 2: Local simulator and baseline metric scoring
Sprint 3: OpenAI structured harness
Sprint 4: Scalable verification runner
Sprint 5: Trace/eval records and dashboard
Sprint 6: MQTT edge loop and canary runtime
Sprint 7: Runtime visualization and trace replay workflows
```

MQTT is still valuable, but the hackathon track rewards engineering depth. The verification runner is now the core differentiator.

## Planned Repository Shape

```text
swarmforge/
  schemas.py
  openai_contract.py
  harness.py
  simulator.py
  verification.py
  scenarios.py
  invariants.py
  risk.py
  traces.py
  ota.py
  topics.py
scripts/
  run_openai_harness.py
  run_verification_matrix.py
  replay_trace_case.py
  export_eval_case.py
docs/
  implementation-steps.md
  sprint-1-product-contract.md
  sprint-2-simulator-plan.md
  sprint-3-openai-harness.md
  sprint-4-verification-runner.md
  sprint-5-trace-dashboard.md
  sprint-6-mqtt-edge-loop.md
```

## What Judges Should Remember

SwarmForge is not trying to make AI "operate the fleet." It is showing a practical pattern for AI-assisted engineering:

```text
Use AI to search and propose.
Use typed contracts to constrain.
Use simulation to falsify.
Use invariants to enforce.
Use traces to audit.
Use canary to bound risk.
```

That is the engineering story.
