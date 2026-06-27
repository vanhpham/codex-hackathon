# Sprint 6.5 / 7: Runtime Visualization and Evidence Surface (Sprint 7)

## Goal

Build a practical operations surface over an already-verified canary runtime:

- live fleet state and health
- node telemetry history
- decision-aware dispatch control
- trace listing and per-trace inspection
- deterministic scenario replay from saved traces

The dashboard is not a control authority.  
The model never publishes OTA directly, never changes rollback policy, and never deploys without an approved `ready_for_canary` decision.

## Why this matters for the hackathon track

This sprint proves we have a system that is inspectable under pressure:

- Verification can be re-run deterministically from traces.
- Dispatch actions are visible at runtime.
- Evaluation evidence is linked to each run.
- The UI is evidence-first rather than marketing-first.

That pattern is harder to fake than a simple config panel.

## Implemented flow

```text
User uploads/creates verified payload
  -> dashboard sends dispatch POST
  -> FleetController checks verification.decision == ready_for_canary
  -> canary nodes are selected and OTA sent
  -> node telemetry is observed for a few samples
  -> evaluation is computed (promote/rollback)
  -> last state/event/evaluation is rendered
```

## Runtime capabilities

- `GET /api/state`: current fleet state, last dispatch, latest evaluation metrics.
- `GET /api/events`: event log (telemetry + dispatch lifecycle).
- `GET /api/traces`: list recent traces from `--trace-dir`.
- `GET /api/trace/<run_id>`: per-run trace summary and scenario list.
- `POST /api/dispatch`: dispatch verified payload to canary nodes.
- `POST /api/replay`: re-run a scenario from a trace.

## Acceptance criteria for Sprint 7 demo

- Dashboard launches with one command and shows live fleet state.
- Cannot dispatch if payload lacks `verification.decision=ready_for_canary`.
- Trace list renders with pass/fail and risk summary.
- Replay call returns deterministic `replayed_result` and `stored_result`.

## Files

- `scripts/sprint7_web.py` – full dashboard + local REST API handlers.
- `scripts/sprint6_web.py` – compatibility shim to keep older command references valid.

## Verification of the demo surface

1. Run a trace run:

```bash
.venv/bin/python scripts/run_verification_matrix.py --scenario-count 50 --adaptive --trace-dir traces
```

2. Start dashboard:

```bash
.venv/bin/python scripts/sprint7_web.py --broker-mode in-memory --node-count 5
```

3. Open the UI, pick a trace, open one run, then replay first failed scenario.

## Handoff after Sprint 7

- Add promotion monitor (non-auto for now).
- Add rollback automation using canary result history.
- Add optional WebSocket stream for smoother real-time charts.
