from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class InvariantFailure:
    name: str
    reason: str
    critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationCaseResult:
    scenario_id: str
    accepted: bool
    failed_invariants: tuple[InvariantFailure, ...]
    metrics: dict[str, float]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "accepted": self.accepted,
            "failed_invariants": [failure.to_dict() for failure in self.failed_invariants],
            "metrics": self.metrics,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RiskReport:
    verification_status: str
    scenario_count: int
    passed_count: int
    failed_count: int
    pass_rate: float
    risk_score: float
    worst_case: dict[str, Any]
    failed_scenarios: tuple[str, ...]
    critical_failures: tuple[str, ...]
    decision: str
    case_results: tuple[VerificationCaseResult, ...]
    executed_scenarios: tuple[dict[str, Any], ...] = ()
    adaptive_cycles: int = 0
    candidate_scenarios: tuple[str, ...] = ()
    adaptive_metadata: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_status": self.verification_status,
            "scenario_count": self.scenario_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "pass_rate": round(self.pass_rate, 4),
            "risk_score": round(self.risk_score, 4),
            "worst_case": self.worst_case,
            "failed_scenarios": list(self.failed_scenarios),
            "critical_failures": list(self.critical_failures),
            "decision": self.decision,
            "executed_scenarios": list(self.executed_scenarios),
            "adaptive_cycles": self.adaptive_cycles,
            "candidate_scenarios": list(self.candidate_scenarios),
            "adaptive_metadata": list(self.adaptive_metadata),
            "case_results": [result.to_dict() for result in self.case_results],
        }


@dataclass(frozen=True)
class SettingSuggestionReport:
    reason: str
    confidence: float
    mutually_exclusive_options: tuple[dict[str, Any], ...]
    risk_delta_preview: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "mutually_exclusive_options": list(self.mutually_exclusive_options),
            "risk_delta_preview": self.risk_delta_preview,
        }
