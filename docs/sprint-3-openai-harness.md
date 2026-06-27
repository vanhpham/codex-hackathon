# Sprint 3: OpenAI Structured Harness

Sprint 3 connects OpenAI Structured Outputs to the local harness. The model proposes a typed `OptimizationPlan`; the harness validates and simulates it.

This sprint is still not a deployment sprint. It produces a safe decision object that Sprint 4 can verify more deeply.

## Sprint Goal

Build this local path:

```text
Engineer prompt
  -> OpenAI Responses API
  -> structured OptimizationPlan
  -> schema and policy validation
  -> baseline simulator
  -> ready_for_verification or blocked
```

The current code returns `ready_for_canary` for accepted baseline simulation. After the Sprint 4 pivot, that status should be treated as "ready for deeper verification" before any real runtime deployment.

## Runtime Contract

Environment variables:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.5
```

Keep real keys in local `.env`. Do not put keys in `.env.example`.

## Model Output Boundary

The model may return only a structured control plan.

It may not:

- deploy
- publish MQTT messages
- execute code
- disable rollback
- bypass canary
- override schema validation
- override simulator or verification rejection

## Implemented Path

```text
scripts/run_openai_harness.py
  -> load .env
  -> OpenAIResponsesPlanClient
  -> responses.parse(..., text_format=OptimizationPlanOutput)
  -> OptimizationPlan.from_dict(...)
  -> simulate_plan(...)
  -> HarnessResult
```

Key files:

```text
swarmforge/openai_contract.py
swarmforge/harness.py
swarmforge/env.py
tests/test_harness.py
```

## Harness Result

Accepted baseline example:

```json
{
  "status": "ready_for_canary",
  "plan_status": "valid",
  "simulation_status": "accepted",
  "deployment_decision": "ready_for_canary",
  "plan": {},
  "simulation_result": {}
}
```

Sprint 4 should wrap or reinterpret this as:

```text
baseline accepted -> run verification matrix -> final canary decision
```

Schema rejection:

```json
{
  "status": "schema_rejected",
  "plan_status": "invalid",
  "simulation_status": "not_started",
  "deployment_decision": "blocked",
  "validation_error": "first deployment must use canary"
}
```

Simulation rejection:

```json
{
  "status": "simulation_rejected",
  "plan_status": "valid",
  "simulation_status": "rejected",
  "deployment_decision": "blocked",
  "simulation_result": {
    "accepted": false,
    "reason": "Filter reduced noise but exceeded the latency budget."
  }
}
```

## Local Commands

Unit tests:

```text
.venv/bin/python -m unittest
```

Live OpenAI SDK smoke test:

```text
.venv/bin/python scripts/run_openai_harness.py
```

Verified Sprint 3 live path:

```text
OpenAI structured plan -> schema valid -> simulation accepted -> ready_for_canary
```

## Test Scenarios

| Scenario | Model Plan | Expected Result |
| --- | --- | --- |
| Happy path | Valid `2Hz` median plan | Accepted baseline |
| Unsafe rollout | Full fleet first action | `schema_rejected` |
| Slow filter | Window `15` with tight latency | `simulation_rejected` |
| Fake model client | No OpenAI network | unit tests pass |

## Definition Of Done

Sprint 3 is complete when:

- OpenAI SDK can produce a structured plan.
- Unit tests run without network or API key.
- Live smoke test can use `.env`.
- Schema failures are blocked before simulation.
- Simulation failures are blocked before verification/deployment.

## Sprint 4 Handoff

Sprint 4 consumes only schema-valid, baseline-accepted plans and runs:

```text
OptimizationPlan
  -> ScenarioMatrix
  -> VerificationRunner
  -> RiskReport
  -> ready_for_canary or blocked
```
