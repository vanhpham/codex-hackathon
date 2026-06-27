# Codex Instructions for SwarmForge Harness

## Project Context

This repository is for **SwarmForge Harness**: an AI-assisted verification control plane for safe edge-swarm operational tuning.

The hackathon track values deep engineering, not a shallow chatbot or simple config manager. The project should be framed as:

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

The guiding principle:

```text
The model proposes. The harness verifies. The harness decides.
```

Do not frame this as:

```text
LLM writes code and deploys it
LLM directly controls nodes
chatbot for IoT configuration
basic config manager
```

## Current Strategic Direction

The project has pivoted from "OTA tuning demo first" to **AI verification harness first**.

The key hackathon story:

```text
Codex/LLM scales engineering search.
The harness enforces typed contracts, invariants, simulation, and auditability.
```

MQTT and edge-node runtime are still useful, but they should come after the scalable verification runner. For the current track, verification depth is more valuable than broker plumbing.

## Revised Build Order

Build in this order unless the user explicitly changes direction:

1. Product contract and typed control plan.
2. Local simulator and baseline metric scoring.
3. OpenAI structured harness.
4. Scalable verification runner.
5. Trace/eval records and dashboard.
6. MQTT edge loop and canary runtime.

Keep every phase independently demoable.

## Preferred Tech Direction

Use this stack unless the user changes direction:

- OpenAI Responses API as the main model interface.
- Structured Outputs for strict `OptimizationPlan` JSON.
- Pydantic for OpenAI output contracts.
- Lightweight dataclass/internal models where already established.
- Python simulator and verification runner.
- Deterministic seeds for replayable scenarios.
- FastAPI and WebSocket dashboard later.
- MQTT with Eclipse Mosquitto later, after verification runner.
- Docker Compose later, after local demo reliability.

## Control Plane Scope

The harness should support schema-controlled operational knobs beyond basic config:

- telemetry sample rate
- collected metrics
- aggregation window
- payload cap
- filter type and window
- power mode
- duty cycle
- sleep interval
- batching
- compression
- retry policy
- MQTT QoS
- log level
- event sampling
- anomaly threshold
- debounce window
- canary percentage
- observation window
- rollback thresholds

The LLM may propose knob values. The harness maps them to trusted implementations.

## Safety Architecture

Prefer this path for MVP:

```text
LLM emits typed control spec -> harness maps spec to trusted implementation
```

Avoid this path unless explicitly requested:

```text
LLM emits arbitrary Python -> backend executes it
```

If generated code mode is added later, require:

- AST validation.
- No imports unless allowlisted.
- No filesystem access.
- No subprocess access.
- No network access.
- No `eval`.
- No unrestricted `exec`.
- Simulation before deployment.
- Canary before full rollout.
- Automatic rollback on health failure.

## Verification Runner Expectations

The scalable verification runner should become the core differentiator.

It should support:

- deterministic scenario generation
- multiple terrain/noise/network/battery/sensor conditions
- many simulation trials per plan
- safety invariant checks
- aggregate pass rate
- worst-case metrics
- failed scenario summaries
- risk score
- `ready_for_canary` or `blocked` decision
- replayable seeds

Important invariants:

- rollback must be enabled
- first rollout must be canary
- latency must stay below rollback budget
- estimated payload must stay below cap
- telemetry health must stay above threshold
- noise-focused plans must reduce noise
- bandwidth-focused plans must reduce bandwidth
- failed scenario rate must stay below threshold

## Documentation Expectations

When updating docs:

- Keep the README judge-friendly and technically deep.
- Emphasize AI-assisted verification, not chatbot behavior.
- Explain why the harness is safer than direct LLM deployment.
- Highlight typed plans, adversarial scenarios, multi-simulation verification, invariants, risk reports, canary boundaries, and trace/eval records.
- Keep sprint docs practical and phase-based.
- If a doc mentions MQTT, make clear it is downstream of verification.

## Code Style Expectations

When code is added:

- Keep modules small and demoable.
- Prefer explicit models and state transitions.
- Avoid premature frameworks.
- Use deterministic seeds for simulator and verification tests.
- Keep tests fast and local by default.
- Do not require network or OpenAI credentials for unit tests.
- Use `.venv/bin/python` and `.venv/bin/pip` for Python commands.

## User Collaboration

The user often wants to approve direction before deeper implementation. If they ask to review tech stack, proposal, README, or instructions, do not jump ahead into unrelated runtime code.

When uncertain, choose the smallest artifact that advances the AI verification harness story without locking the project into unnecessary infrastructure.
