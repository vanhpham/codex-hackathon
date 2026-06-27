# Current State Audit

This document records the real project state after the pivot to **AI-assisted verification harness**.

## Branch And Commit State

Current working branch:

```text
sprint-4-verification-runner
```

Important recent commits:

```text
a39125e feat: add verification scenario models
ef1c8e3 docs: add current state audit
619a62e Merge pull request #2 from vanhpham/sprint-3-openai-harness
cb572ef docs: plan sprint 4 mqtt edge loop
14c2de8 docs: pivot to AI verification harness
```

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
| Sprint 4 | Scalable verification runner | Implemented scenario matrix, invariants, verification runner, risk report, CLI, and tests | Aligned |
| Sprint 5 | Trace/eval records and dashboard | Docs/spec complete, implementation later | Planned |
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
swarmforge/verification.py
scripts/run_openai_harness.py
scripts/run_verification_matrix.py
tests/test_harness.py
tests/test_simulator.py
tests/test_scenarios.py
tests/test_verification.py
requirements.txt
```

These support:

```text
prompt -> OpenAI structured plan -> schema gate -> baseline simulator -> verification matrix -> risk report
```

They do not yet support:

```text
Trace persistence
Dashboard
MQTT runtime
```

That gap is expected after Sprint 4.

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

Sprint 4 smoke command:

```text
.venv/bin/python scripts/run_verification_matrix.py --scenario-count 50
```

Important nuance:

- The committed Sprint 1-4 test suite covers harness, simulator, scenarios, and verification behavior.
- The current workspace also includes untracked Sprint 6 OTA tests, so local test count may include those files until the workspace is cleaned.

## Gaps To Close Next

Sprint 5 implementation should add:

```text
swarmforge/traces.py
swarmforge/evals.py
scripts/replay_trace.py
scripts/export_eval_case.py
```

Minimum Sprint 5 acceptance:

- accepted and blocked runs save trace records
- failed scenario seeds are replayable
- eval-case export exists
- terminal/dashboard summary explains risk report

## Final Audit Verdict

The committed project direction now matches the hackathon track better than the original OTA-first plan.

Status:

```text
Sprints 1-4: aligned and implemented.
Sprint 5-6: planned and documented.
Workspace: one untracked MQTT artifact set should be cleaned or intentionally deferred.
```
