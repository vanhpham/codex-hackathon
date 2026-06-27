# Codex Instructions for SwarmForge Harness

## Project Context

This repository is for **SwarmForge Harness**: a schema-first, simulator-verified LLM control plane for safe OTA tuning across virtual edge swarms.

The project is a hackathon demo focused on the OpenAI API and modern LLM harness design:

```text
Engineer prompt
  -> structured optimization plan
  -> schema validation
  -> local simulation
  -> metric scoring
  -> canary deployment
  -> telemetry monitoring
  -> rollback decision
  -> trace/eval record
```

The guiding principle:

```text
The LLM proposes. The harness decides.
```

Do not frame this as a simple chatbot or direct "LLM writes code and deploys it" project.

## Current Working Mode

- Start with documentation and architecture before implementation.
- Do not scaffold backend, frontend, Docker, or edge-node code unless the user explicitly approves moving into build mode.
- Preserve the current proposal direction in `README.md` and `docs/implementation-steps.md`.
- If asked to brainstorm, stay conceptual and do not edit files unless the user asks for a written artifact.

## Preferred Tech Direction

Use this stack unless the user changes direction:

- OpenAI Responses API as the main model interface.
- Structured Outputs for strict optimization-plan JSON.
- Function/tool calling for harness-owned operations.
- FastAPI backend.
- Pydantic schemas.
- Python edge-node simulators.
- MQTT with Eclipse Mosquitto.
- Custom real-time dashboard first.
- Grafana/InfluxDB only as stretch goals.
- Docker Compose for local orchestration.

## Safety Architecture

Prefer this path for MVP:

```text
LLM emits filter/config spec -> backend maps spec to trusted implementation
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

## Build Order

When implementation begins, build in this order:

1. Schemas.
2. Simulator.
3. OpenAI structured plan call.
4. MQTT one-node loop.
5. Swarm scaling.
6. Canary and rollback.
7. Dashboard.
8. Trace/eval records.

Keep every phase independently demoable.

## Documentation Expectations

When updating docs:

- Keep the README judge-friendly and technically deep.
- Explain why the harness is safer than direct LLM deployment.
- Highlight structured outputs, simulation, canary, rollback, and trace/eval records.
- Keep `docs/implementation-steps.md` practical and phase-based.

## Code Style Expectations

When code is eventually added:

- Keep modules small and easy to explain in a hackathon demo.
- Prefer clear Pydantic models and explicit state transitions.
- Avoid premature abstractions.
- Use async where it helps telemetry or MQTT loops.
- Keep demo reliability above framework cleverness.

## User Collaboration

The user often wants to approve direction before implementation. If they ask to review tech stack, proposal, README, or instructions, do not jump ahead into building runtime code.

When uncertain, choose the smallest artifact that advances the plan without locking the project into unnecessary complexity.
