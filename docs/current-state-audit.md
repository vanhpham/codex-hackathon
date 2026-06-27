# Current State Audit

This document records the real project state after the pivot to **AI-assisted verification harness**.

## Branch And Commit State

Current working branch:

```text
sprint-4-verification-runner
```

Current branch includes the verification hardening stack through Sprint 5 (adaptive + trace).

Interpretation:

- `main` already contains Sprints 1-3.
- `cb572ef` briefly documented MQTT as Sprint 4.
- `14c2de8` pivots the final tree so MQTT is now Sprint 6 and Sprint 4 is the verification runner.
- The final file tree is aligned with the new strategy, even though branch history contains the earlier MQTT planning commit.

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
| Sprint 6 | MQTT edge loop and canary runtime | Docs/spec moved from old Sprint 4, implementation later | Planned |

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
tests/test_harness.py
tests/test_simulator.py
tests/test_scenarios.py
tests/test_verification.py
tests/test_adaptive_verification.py
tests/test_setting_suggester.py
tests/test_verification_adaptive.py
requirements.txt
```

These support:

```text
prompt -> OpenAI structured plan -> schema gate -> baseline simulator -> verification matrix -> risk report
```

They do not yet support:

```text
Live dashboard UI
MQTT runtime
```

That gap is expected as Sprint 6 hardening is next.

## Known Workspace Issue

There are untracked files from the earlier MQTT-first path:

```text
swarmforge/ota.py
swarmforge/topics.py
tests/test_ota.py
```

They are not part of the committed Sprint 4 verification pivot. They can be:

- deleted now if we want a clean Sprint 4 verification branch, or
- kept untracked and reused later in Sprint 6.

Recommended choice:

```text
Keep them untracked for now, and promote them intentionally in Sprint 6.
Do not include them in the Sprint 4 verification commit.
```

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

- The committed Sprint 1-4 test suite covers harness, simulator, scenarios, and verification behavior.
- The current workspace also includes untracked Sprint 6 OTA tests, so local test count may include those files until the workspace is cleaned.

## Gaps To Close Next

Sprint 6 implementation should add:

- ota payload mapping
- canary edge dispatch
- deployment guardrails with real runtime feedback

## Final Audit Verdict

The committed project direction now matches the hackathon track better than the original OTA-first plan.

Status:

```text
Sprints 1-5: aligned and implemented.
Sprint 6: planned and documented.
Workspace: one untracked MQTT artifact set should be cleaned or intentionally deferred.
```
