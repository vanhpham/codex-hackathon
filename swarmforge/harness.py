from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass
import json
from typing import Protocol

from swarmforge.openai_contract import OptimizationPlanOutput
from swarmforge.schemas import OptimizationPlan, ValidationError
from swarmforge.simulator import simulate_plan


SYSTEM_INSTRUCTIONS = """You are the planning component inside SwarmForge Harness.
Convert the engineer request into one safe OptimizationPlan.
The model proposes only; the harness validates, simulates, and decides.

Rules:
- Emit only schema-conforming plan fields.
- First deployment must be canary.
- Rollback must be enabled.
- Do not request full-fleet deployment.
- Do not generate code.
- Prefer trusted filter specs over arbitrary logic.
- For the muddy terrain accelerometer demo, prefer a 2Hz median-filtered plan unless the prompt asks otherwise.
"""


class PlanClient(Protocol):
    def create_plan(self, prompt: str) -> dict:
        """Return a raw OptimizationPlan-shaped dictionary."""


@dataclass(frozen=True)
class HarnessResult:
    run_id: str
    status: str
    plan_status: str
    simulation_status: str
    deployment_decision: str
    raw_plan_json: str | None = None
    plan: dict | None = None
    simulation_result: dict | None = None
    validation_error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class OpenAIResponsesPlanClient:
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        from openai import OpenAI

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def create_plan(self, prompt: str) -> dict:
        response = self.client.responses.parse(
            model=self.model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=prompt,
            text_format=OptimizationPlanOutput,
            max_output_tokens=1600,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI response did not include a parsed OptimizationPlan")
        return parsed.model_dump()


def run_harness(prompt: str, plan_client: PlanClient, run_id: str | None = None) -> HarnessResult:
    run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    raw_plan = plan_client.create_plan(prompt)
    raw_plan_json: str | None = None
    if isinstance(raw_plan, (dict, list)):
        try:
            raw_plan_json = json.dumps(raw_plan, indent=2, sort_keys=True)
        except TypeError:
            raw_plan_json = None
    elif isinstance(raw_plan, str):
        raw_plan_json = raw_plan

    try:
        plan = OptimizationPlan.from_dict(raw_plan)
    except (TypeError, ValueError, ValidationError) as exc:
        return HarnessResult(
            run_id=run_id,
            status="schema_rejected",
            plan_status="invalid",
            simulation_status="not_started",
            deployment_decision="blocked",
            plan=raw_plan if isinstance(raw_plan, dict) else None,
            raw_plan_json=raw_plan_json,
            validation_error=str(exc),
        )

    simulation = simulate_plan(plan)
    if not simulation.accepted:
        return HarnessResult(
            run_id=run_id,
            status="simulation_rejected",
            plan_status="valid",
            simulation_status="rejected",
            deployment_decision="blocked",
            plan=raw_plan,
            raw_plan_json=raw_plan_json,
            simulation_result=simulation.to_dict(),
        )

    return HarnessResult(
        run_id=run_id,
        status="ready_for_canary",
        plan_status="valid",
        simulation_status="accepted",
        deployment_decision="ready_for_canary",
        plan=raw_plan,
        raw_plan_json=raw_plan_json,
        simulation_result=simulation.to_dict(),
    )
