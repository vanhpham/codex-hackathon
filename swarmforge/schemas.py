from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Intent = Literal[
    "reduce_noise",
    "reduce_bandwidth",
    "reduce_noise_and_bandwidth",
    "improve_battery_life",
    "stabilize_telemetry",
]
TargetMetric = Literal[
    "accelerometer",
    "temperature",
    "battery",
    "bandwidth",
    "telemetry_health",
]
FilterType = Literal["none", "moving_average", "median", "low_pass"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
PublishMode = Literal["raw", "summary", "summary_and_anomalies", "anomalies_only"]


ALLOWED_INTENTS = {
    "reduce_noise",
    "reduce_bandwidth",
    "reduce_noise_and_bandwidth",
    "improve_battery_life",
    "stabilize_telemetry",
}
ALLOWED_TARGET_METRICS = {
    "accelerometer",
    "temperature",
    "battery",
    "bandwidth",
    "telemetry_health",
}
ALLOWED_FILTERS = {"none", "moving_average", "median", "low_pass"}
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
ALLOWED_TELEMETRY_METRICS = {
    "accelerometer",
    "temperature",
    "battery",
    "bandwidth",
    "telemetry_health",
    "error_count",
    "config_version",
}
ALLOWED_PUBLISH_MODES = {
    "raw",
    "summary",
    "summary_and_anomalies",
    "anomalies_only",
}


class ValidationError(ValueError):
    """Raised when a plan violates the Sprint 1 contract."""


@dataclass(frozen=True)
class FilterSpec:
    type: FilterType
    window_size: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FilterSpec":
        filter_type = data.get("type")
        window_size = int(data.get("window_size", 1))

        if filter_type not in ALLOWED_FILTERS:
            raise ValidationError("filter.type must be allowlisted")
        if window_size < 1 or window_size > 15:
            raise ValidationError("filter.window_size must be between 1 and 15")
        if filter_type == "median" and window_size % 2 == 0:
            raise ValidationError("filter.window_size must be odd for median")
        if filter_type in {"moving_average", "median"} and window_size < 1:
            raise ValidationError("filter.window_size is required")

        return cls(type=filter_type, window_size=window_size)


@dataclass(frozen=True)
class TelemetryCollection:
    metrics: tuple[str, ...]
    aggregation_window_seconds: int
    publish_mode: PublishMode
    max_payload_kbps: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetryCollection":
        metrics = tuple(data.get("metrics", ()))
        aggregation_window_seconds = int(data.get("aggregation_window_seconds", 0))
        publish_mode = data.get("publish_mode")
        max_payload_kbps = float(data.get("max_payload_kbps", 0))

        if not metrics:
            raise ValidationError("telemetry_collection.metrics must include at least one metric")
        if any(metric not in ALLOWED_TELEMETRY_METRICS for metric in metrics):
            raise ValidationError("telemetry_collection.metrics must be allowlisted")
        if publish_mode not in ALLOWED_PUBLISH_MODES:
            raise ValidationError("telemetry_collection.publish_mode must be allowlisted")
        if aggregation_window_seconds < 1 or aggregation_window_seconds > 60:
            raise ValidationError(
                "telemetry_collection.aggregation_window_seconds must be between 1 and 60"
            )
        if max_payload_kbps < 1 or max_payload_kbps > 64:
            raise ValidationError("telemetry_collection.max_payload_kbps must be between 1 and 64")

        return cls(
            metrics=metrics,
            aggregation_window_seconds=aggregation_window_seconds,
            publish_mode=publish_mode,
            max_payload_kbps=max_payload_kbps,
        )


@dataclass(frozen=True)
class RollbackPolicy:
    enabled: bool
    max_latency_ms: float
    max_error_rate: float
    min_telemetry_health: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RollbackPolicy":
        enabled = bool(data.get("enabled", False))
        max_latency_ms = float(data.get("max_latency_ms", 0))
        max_error_rate = float(data.get("max_error_rate", 0))
        min_telemetry_health = float(data.get("min_telemetry_health", 0))

        if not enabled:
            raise ValidationError("rollback.enabled must be true")
        if max_latency_ms < 50 or max_latency_ms > 1000:
            raise ValidationError("rollback.max_latency_ms must be between 50 and 1000")
        if max_error_rate < 0 or max_error_rate > 0.2:
            raise ValidationError("rollback.max_error_rate must be between 0 and 0.2")
        if min_telemetry_health < 0.8 or min_telemetry_health > 1.0:
            raise ValidationError("rollback.min_telemetry_health must be between 0.8 and 1.0")

        return cls(
            enabled=enabled,
            max_latency_ms=max_latency_ms,
            max_error_rate=max_error_rate,
            min_telemetry_health=min_telemetry_health,
        )


@dataclass(frozen=True)
class DeploymentSpec:
    strategy: str
    percentage: float
    observation_window_seconds: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeploymentSpec":
        strategy = data.get("strategy")
        percentage = float(data.get("percentage", 0))
        observation_window_seconds = int(data.get("observation_window_seconds", 0))

        if strategy != "canary":
            raise ValidationError("first deployment must use canary")
        if percentage < 1 or percentage > 20:
            raise ValidationError("deployment.percentage must be between 1 and 20")
        if observation_window_seconds < 5 or observation_window_seconds > 30:
            raise ValidationError(
                "deployment.observation_window_seconds must be between 5 and 30"
            )

        return cls(
            strategy=strategy,
            percentage=percentage,
            observation_window_seconds=observation_window_seconds,
        )


@dataclass(frozen=True)
class OptimizationPlan:
    intent: Intent
    target_metric: TargetMetric
    sampling_rate_hz: float
    log_level: LogLevel
    filter: FilterSpec
    telemetry_collection: TelemetryCollection
    deployment: DeploymentSpec
    rollback: RollbackPolicy

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OptimizationPlan":
        intent = data.get("intent")
        target_metric = data.get("target_metric")
        sampling_rate_hz = float(data.get("sampling_rate_hz", 0))
        log_level = data.get("log_level")

        if intent not in ALLOWED_INTENTS:
            raise ValidationError("intent must be allowlisted")
        if target_metric not in ALLOWED_TARGET_METRICS:
            raise ValidationError("target_metric must be allowlisted")
        if sampling_rate_hz < 1 or sampling_rate_hz > 20:
            raise ValidationError("sampling_rate_hz must be between 1 and 20")
        if log_level not in ALLOWED_LOG_LEVELS:
            raise ValidationError("log_level must be allowlisted")

        return cls(
            intent=intent,
            target_metric=target_metric,
            sampling_rate_hz=sampling_rate_hz,
            log_level=log_level,
            filter=FilterSpec.from_dict(data.get("filter", {})),
            telemetry_collection=TelemetryCollection.from_dict(
                data.get("telemetry_collection", {})
            ),
            deployment=DeploymentSpec.from_dict(data.get("deployment", {})),
            rollback=RollbackPolicy.from_dict(data.get("rollback", {})),
        )


@dataclass(frozen=True)
class BaselineConfig:
    sampling_rate_hz: float = 10
    log_level: LogLevel = "INFO"
    filter: FilterSpec = FilterSpec(type="none", window_size=1)
    telemetry_collection: TelemetryCollection = TelemetryCollection(
        metrics=("accelerometer", "temperature", "battery", "bandwidth"),
        aggregation_window_seconds=1,
        publish_mode="raw",
        max_payload_kbps=32,
    )


@dataclass(frozen=True)
class SimulationResult:
    accepted: bool
    reason: str
    noise_score_before: float
    noise_score_after: float
    noise_reduction_ratio: float
    bandwidth_before_kbps: float
    bandwidth_after_kbps: float
    bandwidth_reduction_ratio: float
    latency_penalty_ms: float
    payload_limit_kbps: float
    estimated_payload_kbps: float
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "noise_score_before": round(self.noise_score_before, 4),
            "noise_score_after": round(self.noise_score_after, 4),
            "noise_reduction_ratio": round(self.noise_reduction_ratio, 4),
            "bandwidth_before_kbps": round(self.bandwidth_before_kbps, 4),
            "bandwidth_after_kbps": round(self.bandwidth_after_kbps, 4),
            "bandwidth_reduction_ratio": round(self.bandwidth_reduction_ratio, 4),
            "latency_penalty_ms": round(self.latency_penalty_ms, 2),
            "payload_limit_kbps": round(self.payload_limit_kbps, 4),
            "estimated_payload_kbps": round(self.estimated_payload_kbps, 4),
            "score": round(self.score, 4),
        }

