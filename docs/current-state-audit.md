# Current State Audit

This document records the real project state after the pivot to **AI-assisted verification harness**.

## Branch And Commit State

Current working branch:

```text
sprint-6
```

Current branch includes the verification hardening stack through Sprint 6.

Interpretation:

- `sprint-6` now includes Sprints 1-6.
- Branch history contains earlier pivot commits (`14c2de8` and later hardening commits).
- The tree is aligned with the new strategy from a real end-to-end local canary loop.

If a clean PR history matters later, squash or rebase the branch before opening a PR. Do not do that without explicit user approval.

## Current Sprint Alignment

| Sprint | Intended Outcome | Current State | Alignment |
| --- | --- | --- | --- |
| Sprint 1 | Product contract and typed control plan | Docs updated for AI verification harness and broader control knobs | Aligned |
| Sprint 2 | Local simulator and baseline scoring | Implemented simulator, scoring, and tests | Aligned |
| Sprint 3 | OpenAI structured harness | Implemented Responses API structured plan path, fake-client tests, live smoke command | Aligned |
| Sprint 4 | Scalable verification runner | Implemented scenario matrix, invariants, risk report, CLI, and tests | Aligned |
| Sprint 4.5 | Adaptive verification + suggestions | Added bounded adaptive generation, worker pool, suggestion engine, and reporting metadata | Completed |
| Sprint 5 | Trace/eval records and dashboard | Trace persistence, replay, and eval export are implemented | Completed |
| Sprint 6 | MQTT edge loop and canary runtime | Docker-backed transport, web runtime dashboard, and node agent flow are implemented | Completed |

## Current Code State

Committed and aligned:

```text
swarmforge/openai_contract.py
swarmforge/harness.py
swarmforge/env.py
swarmforge/schemas.py
swarmforge/simulator.py
swarmforge/scenarios.py
swarmforge/invariants.py
swarmforge/risk.py
swarmforge/adaptive_verification.py
swarmforge/setting_suggester.py
swarmforge/verification.py
swarmforge/traces.py
scripts/run_openai_harness.py
scripts/run_verification_matrix.py
scripts/replay_trace_case.py
scripts/export_eval_case.py
swarmforge/ota.py
swarmforge/topics.py
swarmforge/edge_runtime.py
swarmforge/mqtt_transport.py
scripts/run_canary_demo.py
scripts/mqtt_node_agent.py
scripts/run_sprint6_nodes.py
scripts/sprint6_web.py
tests/test_harness.py
tests/test_simulator.py
tests/test_scenarios.py
tests/test_verification.py
tests/test_adaptive_verification.py
tests/test_setting_suggester.py
tests/test_verification_adaptive.py
tests/test_ota.py
tests/test_edge_runtime.py
tests/test_run_canary_demo.py
docker/docker-compose.yml
docker/mosquitto.conf
requirements.txt
``` 

These support:

```text
prompt -> OpenAI structured plan -> schema gate -> baseline simulator -> verification matrix -> risk report
```

They also support:

```text
Docker-backed MQTT transport (`swarmforge.mqtt_transport`, `docker/docker-compose.yml`)
web dashboard (`scripts/sprint6_web.py`)
standalone node agents (`scripts/mqtt_node_agent.py`, `scripts/run_sprint6_nodes.py`)
```

Live Docker validation is expected in environments where Docker daemon access is available.

## Known Workspace Issue

Current environment cannot execute Docker transport smoke checks (daemon/socket access is unavailable),  
so live runtime verification is validated by contract/unit tests and documented runbook instead.

## Current Verification

Unit tests currently pass in the local workspace:

```text
.venv/bin/python -m unittest
```

Trace + replay command:

```bash
.venv/bin/python scripts/run_verification_matrix.py --scenario-count 50 --trace-dir traces
.venv/bin/python scripts/replay_trace_case.py traces/<run_id>.json --scenario-id <scenario_id>
.venv/bin/python scripts/export_eval_case.py traces/<run_id>.json --out eval_case.json
```

Important nuance:

- The committed suite covers harness, simulator, scenarios, verification, trace replay, and canary runtime behavior.
- Full suite runs in-place with `.venv` dependencies and the in-memory broker path.

## Gaps To Close Next

Sprint 7+ scope:

- promotion monitor and rollback automation
- richer dashboard observability and promotion workflows

## Final Audit Verdict

The committed project direction now matches the hackathon track: verifier-first control plane with a bounded local canary runtime.

Status:

```text
Sprints 1-6: aligned and implemented.
Sprint 6 now includes runnable Docker-backed transport, node agents, and web dashboard entrypoints.
```
