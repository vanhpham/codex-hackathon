# SwarmForge Harness Implementation Steps

This roadmap reflects the updated hackathon strategy: SwarmForge is an **AI-assisted verification control plane**, not a simple OTA config manager.

The core flow:

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

## Sprint Map

```text
Sprint 1: Product contract and typed control plan
Sprint 2: Local simulator and baseline metric scoring
Sprint 3: OpenAI structured harness
Sprint 4: Scalable verification runner
Sprint 5: Trace/eval records and dashboard
Sprint 6: MQTT edge loop and canary runtime
```

Sprint docs:

```text
docs/current-state-audit.md
docs/sprint-1-product-contract.md
docs/sprint-2-simulator-plan.md
docs/sprint-3-openai-harness.md
docs/sprint-4-verification-runner.md
docs/sprint-5-trace-dashboard.md
docs/sprint-6-mqtt-edge-loop.md
```

## Strategic Rationale

For the hackathon track, the strongest engineering signal is not "we can publish config over MQTT." The stronger signal is:

```text
One prompt becomes a typed plan.
The plan is stress-tested across many deterministic edge scenarios.
The harness produces a risk report with auditable reasons.
Only safe plans can approach deployment.
```

MQTT remains part of the final control-plane story, but verification depth comes first.

## Sprint 1: Product Contract And Typed Control Plan

Goal:

```text
Define the problem, safety boundary, control knobs, and typed OptimizationPlan.
```

Primary outputs:

- product thesis
- typed plan contract
- allowed operational knobs
- schema/policy constraints
- accepted/rejected examples
- run-state draft

Key requirements:

- The model may propose a plan only.
- The harness owns validation, simulation, verification, and deployment decisions.
- Rollback must be enabled.
- First deployment must be canary.
- Config/code execution paths must stay separate.

Status:

```text
Complete, but updated docs should keep expanding the plan beyond basic config fields.
```

## Sprint 2: Local Simulator And Baseline Metric Scoring

Goal:

```text
Prove one plan can be measured locally before any OpenAI or MQTT runtime matters.
```

Primary outputs:

- deterministic accelerometer signal
- trusted filter implementations
- bandwidth estimate
- latency estimate
- simple scoring
- accepted/rejected simulation result

Key requirements:

- Tests run without network.
- Median filter happy path is accepted.
- Oversized filter is rejected.
- Payload cap violations are rejected.
- No-useful-change plans are rejected.

Status:

```text
Complete baseline. Sprint 4 generalizes this into scenario-matrix verification.
```

## Sprint 3: OpenAI Structured Harness

Goal:

```text
Connect OpenAI Structured Outputs to the local schema and simulator gates.
```

Primary outputs:

- Pydantic output contract
- OpenAI Responses API adapter
- local `.env` loader
- harness runner
- fake-client unit tests
- live OpenAI SDK smoke test

Key requirements:

- Unit tests must not require network or API keys.
- Live smoke test may use `.env`.
- Model returns only a typed plan.
- Harness blocks schema failures.
- Harness blocks simulator failures.

Status:

```text
Complete and merged to main.
```

## Sprint 4: Scalable Verification Runner

Goal:

```text
Turn one valid plan into many adversarial simulations and a risk report.
```

Primary outputs:

- `ScenarioSpec`
- `ScenarioMatrix`
- `SafetyInvariant`
- `VerificationRunner`
- `RiskReport`
- CLI runner for verification matrix
- tests for pass/fail aggregation
- adaptive counterexample pipeline (optional)
- candidate metadata + suggestions report integration

Key requirements:

- Deterministic seeds.
- Configurable scenario count.
- Terrain/noise/network/battery/sensor variants.
- Per-scenario simulation outputs.
- Invariant failures captured with reasons.
- Aggregated pass rate and risk score.
- Final decision: `ready_for_canary` or `blocked`.
- Adaptive mode with optional worker pool and bounded adaptive rounds.
- Candidate suggestions must keep hard bounds.

Acceptance:

```text
Complete. Good plan passes the verification matrix.
Risky plan fails specific scenarios with clear reasons.
Adaptive candidates are bounded, replayable, and policy-driven.
Runner can execute 50+ local simulations quickly.
Risk report is JSON-serializable and replayable.
```

## Sprint 4.5: Adaptive Verification And Suggestion

Goal:

```text
Move from static matrix replay to policy-driven adaptive stress and safe setting recommendations.
```

Primary outputs:

- `adaptive_verification.py` for bounded counterexample candidates
- `setting_suggester.py` for mutually-exclusive settings proposals
- Worker-pool execution for batch verification
- Adaptive report metadata for replay and audit

Acceptance:

```text
Adaptive mode is disabled by default.
LLM scenario generation is bounded and schema-validated.
LLM-down mode still completes via deterministic fallback.
Suggestions only use safe options within established constraints.
```

## Sprint 5: Trace/Eval Records And Dashboard

Goal:

```text
Make the verification story inspectable, replayable, and demo-friendly.
```

Primary outputs:

- durable run trace JSON
- eval-case export format
- replay command
- lightweight dashboard or terminal report
- run timeline
- risk report visualization

Key requirements:

  - Every run records prompt, model plan, schema result, verification matrix, risk report, and final decision.
  - Failed scenarios can be replayed by seed.
  - Adaptive and suggestion metadata are included in stored traces.
- Demo can show the difference between schema rejection and verification rejection.
- Dashboard should emphasize engineering evidence, not marketing UI.

Acceptance:

```text
Sprint5 run artifacts can be inspected after every verification execution.
Successful and blocked verification outcomes are both saved as traces.
Replay command reproduces a failed scenario.
Eval export includes scenario-level input/expected metadata.
```

## Sprint 6: MQTT Edge Loop And Canary Runtime

Goal:

```text
Connect only verified `ready_for_canary` decisions to a bounded edge runtime.
```

Primary outputs:

- trusted OTA payload mapping
- MQTT topic helpers
- one virtual edge agent
- targeted node dispatch
- config-applied and config-rejected events
- simple canary selection

Key requirements:

- Only `ready_for_canary` results can dispatch.
- Rejected plans cannot become MQTT payloads.
- The edge node validates config before applying.
- Config applies without process restart.
- Telemetry and event topics follow the documented contract.

Acceptance:

```text
One node receives a trusted OTA config.
Node updates runtime config and emits config_applied.
Invalid config emits config_rejected.
No full-fleet deployment exists before canary.
```

## Stretch Work

Add only after the core verification story is strong:

- multi-candidate plan ranking
- Codex-generated adversarial scenario proposals
- OpenAI eval dataset export
- generated filter code with AST validator
- FastAPI API surface
- WebSocket dashboard
- Docker Compose
- Mosquitto MQTT runtime
- 50-100 virtual nodes
- Grafana/InfluxDB

## Current Recommended Next Step

Stop building MQTT-first runtime. Build Sprint 4:

```text
ScenarioSpec -> ScenarioMatrix -> VerificationRunner -> RiskReport
```

This is the pivot that makes SwarmForge fit the engineering-depth track.
