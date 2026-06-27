# Sprint 5: Trace/Eval Records And Dashboard

Sprint 5 makes the verification harness inspectable and demo-friendly.

The Sprint 5 thesis:

```text
Engineering depth only matters if judges can inspect the evidence.
```

## Sprint Goal

Persist and display:

```text
prompt
model plan
schema result
baseline simulation
scenario matrix
verification case results
risk report
final decision
```

## Trace Record

Every run should produce a JSON record:

```json
{
  "run_id": "run_001",
  "prompt": "...",
  "model": "gpt-5.5",
  "model_plan": {},
  "schema_result": {
    "status": "passed"
  },
  "baseline_simulation": {},
  "verification": {
    "scenario_count": 500,
    "pass_rate": 0.962,
    "risk_score": 0.18,
    "decision": "ready_for_canary"
  },
  "failed_scenarios": [],
  "created_at": "2026-06-27T00:00:00Z"
}
```

## Eval Export

Each trace can become an eval case:

```json
{
  "input": {
    "prompt": "Reduce noisy accelerometer telemetry."
  },
  "expected": {
    "schema_status": "passed",
    "verification_decision": "ready_for_canary"
  },
  "metadata": {
    "scenario_count": 500,
    "risk_score": 0.18
  }
}
```

## Dashboard Requirement

The dashboard should show engineering evidence, not a marketing landing page.

Panels:

- prompt and model plan
- schema gate status
- verification run progress
- scenario pass/fail count
- risk score
- worst-case scenario
- failed invariant list
- final decision
- trace download/replay id

Minimum viable dashboard can be terminal-first if web UI would slow the core demo.

## Replay Requirement

Add a replay path:

```text
run_id -> failed scenario seed -> rerun simulator -> same result
```

This is a strong judge moment because it proves the harness is inspectable.

## Test Scenarios

| Scenario | Expected Result |
| --- | --- |
| Accepted run | trace saved |
| Blocked run | trace saved with reasons |
| Failed scenario | replay seed stored |
| Eval export | JSON eval case generated |
| Dashboard data | summary object includes risk report |

## Definition Of Done

Sprint 5 is complete when:

- every verification run creates a trace
- accepted and blocked examples are saved
- failed scenarios can be replayed by seed
- eval export exists
- dashboard/terminal report explains the final decision clearly

## Handoff

Sprint 6 consumes only trace-backed `ready_for_canary` risk reports for MQTT runtime.
