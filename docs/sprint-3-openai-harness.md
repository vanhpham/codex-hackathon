# Sprint 3: OpenAI Structured Harness

Sprint 3 connects the schema and simulator from Sprints 1-2 to an OpenAI model call. The model is allowed to propose an `OptimizationPlan`; the harness still owns validation, simulation, and the final deployment decision.

The Sprint 3 thesis:

```text
The model emits a constrained plan.
The harness validates and simulates before any OTA action exists.
```

## Sprint Goal

Build a local harness path:

```text
Engineer prompt
  -> OpenAI Responses API structured output
  -> OptimizationPlan validation
  -> local simulator
  -> ready_for_canary or rejected decision
```

Sprint 3 does not deploy to MQTT, edge nodes, or Docker. It only prepares a safe decision object that Sprint 4 can consume.

## Runtime Contract

Environment variables:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.5
```

`OPENAI_MODEL` should remain configurable so the demo can use the latest available high-capability model without code changes.

Keep real keys in local `.env`. Do not put keys in `.env.example`.

## Harness Input

```json
{
  "prompt": "Xe dang vao vung bun lay, rung lac manh. Hay giam sample rate xuong 2Hz, them median filter cho gia toc, va chuyen log level sang WARNING.",
  "mode": "safe"
}
```

## Model Output Boundary

The model may return only a structured `OptimizationPlan`.

It may not:

- call deployment functions
- publish MQTT messages
- execute code
- disable rollback
- bypass canary
- request full-fleet rollout as the first action

## Harness Output

Accepted example:

```json
{
  "run_id": "run_local_001",
  "status": "ready_for_canary",
  "plan_status": "valid",
  "simulation_status": "accepted",
  "deployment_decision": "ready_for_canary",
  "plan": {},
  "simulation_result": {}
}
```

Rejected example:

```json
{
  "run_id": "run_local_002",
  "status": "simulation_rejected",
  "plan_status": "valid",
  "simulation_status": "rejected",
  "deployment_decision": "blocked",
  "plan": {},
  "simulation_result": {
    "accepted": false,
    "reason": "Filter reduced noise but exceeded the latency budget."
  }
}
```

Schema rejection example:

```json
{
  "run_id": "run_local_003",
  "status": "schema_rejected",
  "plan_status": "invalid",
  "simulation_status": "not_started",
  "deployment_decision": "blocked",
  "validation_error": "first deployment must use canary"
}
```

## Implementation Notes

- Use the Responses API as the model interface.
- Use Structured Outputs so the response is constrained to the `OptimizationPlan` JSON schema.
- Keep the OpenAI client behind a small adapter so tests can use a fake model client.
- Do not require network or API keys for unit tests.
- Keep schema validation and simulation local.
- Do not introduce FastAPI or MQTT yet.

## Test Scenarios

| Scenario | Model Plan | Expected Result |
| --- | --- | --- |
| Happy path | Valid `2Hz` median plan | `ready_for_canary` |
| Unsafe rollout | Full fleet first action | `schema_rejected` |
| Slow filter | Window `15` with tight latency | `simulation_rejected` |
| Malformed JSON | Missing required fields | `schema_rejected` |

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

## Definition of Done

Sprint 3 is complete when:

- A prompt can be passed to a harness runner.
- The OpenAI adapter can request a structured `OptimizationPlan`.
- Unit tests can run with a fake model client and no network.
- Valid model plans pass into the Sprint 2 simulator.
- Invalid model plans are rejected before simulation.
- Simulator failures block deployment.
- No OTA/MQTT side effect exists yet.

## Sprint 4 Handoff

Sprint 4 should consume only `ready_for_canary` harness results.

```text
ready_for_canary -> select canary nodes -> dispatch MQTT config -> monitor -> promote/rollback
```
