from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from swarmforge.risk import RiskReport
from swarmforge.scenarios import ScenarioSpec
from swarmforge.schemas import OptimizationPlan
from swarmforge.setting_suggester import SettingSuggestionReport
from swarmforge.verification import run_verification_case


def make_run_id() -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{timestamp}"


@dataclass(frozen=True)
class VerificationTrace:
    run_id: str
    created_at: str
    plan: dict[str, Any]
    verification: dict[str, Any]
    scenario_records: tuple[dict[str, Any], ...]
    model: str | None = None
    prompt: str | None = None
    setting_suggestions: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "model": self.model,
            "prompt": self.prompt,
            "plan": self.plan,
            "verification": self.verification,
            "scenario_records": list(self.scenario_records),
            "setting_suggestions": self.setting_suggestions,
        }

    @property
    def failed_scenario_ids(self) -> tuple[str, ...]:
        return tuple(
            record["scenario"]["scenario_id"]
            for record in self.scenario_records
            if not record["result"]["accepted"]
        )


def build_verification_trace(
    plan: OptimizationPlan,
    report: RiskReport,
    scenarios: tuple[ScenarioSpec, ...],
    *,
    run_id: str,
    model: str | None = None,
    prompt: str | None = None,
    setting_suggestion: SettingSuggestionReport | None = None,
) -> VerificationTrace:
    plan_dict = {
        "intent": plan.intent,
        "target_metric": plan.target_metric,
        "sampling_rate_hz": plan.sampling_rate_hz,
        "log_level": plan.log_level,
        "filter": plan.filter.__dict__,
        "telemetry_collection": {
            **plan.telemetry_collection.__dict__,
            "metrics": list(plan.telemetry_collection.metrics),
        },
        "deployment": plan.deployment.__dict__,
        "rollback": plan.rollback.__dict__,
    }

    result_map = {result.scenario_id: result for result in report.case_results}
    scenario_records: list[dict[str, Any]] = []

    for scenario in scenarios:
        result = result_map.get(scenario.scenario_id)
        if result is None:
            continue
        scenario_records.append(
            {
                "scenario": scenario.to_dict(),
                "result": result.to_dict(),
            }
        )

    return VerificationTrace(
        run_id=run_id,
        created_at=datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        plan=plan_dict,
        verification=report.to_dict(),
        scenario_records=tuple(scenario_records),
        model=model,
        prompt=prompt,
        setting_suggestions=(
            setting_suggestion.to_dict() if setting_suggestion is not None else None
        ),
    )


def build_eval_case(trace: VerificationTrace, scenario_id: str | None = None) -> dict[str, Any]:
    target_scenario_id = scenario_id
    if target_scenario_id is None:
        target = next(
            (record for record in trace.scenario_records if not record["result"]["accepted"]),
            trace.scenario_records[0] if trace.scenario_records else None,
        )
        if target is None:
            raise ValueError("No scenarios recorded in trace")
        target_scenario_id = target["scenario"]["scenario_id"]

    expected = {
        "schema_status": "passed",  # verification path implies schema/sim baseline path was successful.
        "verification_decision": trace.verification.get("decision", "unknown"),
        "risk_score": trace.verification.get("risk_score", 1.0),
        "pass_rate": trace.verification.get("pass_rate", 0.0),
    }

    return {
        "input": {
            "prompt": trace.prompt or "",
            "scenario_id": target_scenario_id,
            "model": trace.model,
        },
        "expected": expected,
        "metadata": {
            "run_id": trace.run_id,
            "created_at": trace.created_at,
            "scenario_count": trace.verification.get("scenario_count", 0),
            "adaptive_cycles": trace.verification.get("adaptive_cycles", 0),
            "candidate_scenarios": trace.verification.get("candidate_scenarios", []),
        },
        "recording": {
            "status": "failed" if target_scenario_id in trace.failed_scenario_ids else "passed",
            "run_result": trace.verification.get("decision", "blocked"),
        },
    }


def save_trace(trace: VerificationTrace, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(trace.to_dict(), file, indent=2, sort_keys=True)
    return path


def load_trace(path: str | Path) -> VerificationTrace:
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    return VerificationTrace(
        run_id=data["run_id"],
        created_at=data["created_at"],
        model=data.get("model"),
        prompt=data.get("prompt"),
        plan=data["plan"],
        verification=data["verification"],
        scenario_records=tuple(data.get("scenario_records", [])),
        setting_suggestions=data.get("setting_suggestions"),
    )


def find_case(trace: VerificationTrace, scenario_id: str) -> dict[str, Any]:
    for record in trace.scenario_records:
        if record["scenario"]["scenario_id"] == scenario_id:
            return record
    raise KeyError(f"scenario_id not found in trace: {scenario_id}")


def replay_trace_case(trace: VerificationTrace, scenario_id: str) -> dict[str, Any]:
    record = find_case(trace, scenario_id)

    scenario = ScenarioSpec(**record["scenario"])
    plan = OptimizationPlan.from_dict(trace.plan)
    replayed = run_verification_case(plan, scenario)
    replayed_payload = replayed.to_dict()

    return {
        "trace": trace.to_dict(),
        "requested_scenario_id": scenario_id,
        "replayed_result": replayed_payload,
        "stored_result": record["result"],
        "matches": replayed_payload == record["result"],
    }
