from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FilterSpecOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["none", "moving_average", "median", "low_pass"]
    window_size: int = Field(ge=1, le=15)


class TelemetryCollectionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: list[
        Literal[
            "accelerometer",
            "temperature",
            "battery",
            "bandwidth",
            "telemetry_health",
            "error_count",
            "config_version",
        ]
    ] = Field(min_length=1)
    aggregation_window_seconds: int = Field(ge=1, le=60)
    publish_mode: Literal["raw", "summary", "summary_and_anomalies", "anomalies_only"]
    max_payload_kbps: float = Field(ge=1, le=64)


class DeploymentSpecOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["canary"]
    percentage: float = Field(ge=1, le=20)
    observation_window_seconds: int = Field(ge=5, le=30)


class RollbackPolicyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: Literal[True]
    max_latency_ms: float = Field(ge=50, le=1000)
    max_error_rate: float = Field(ge=0, le=0.2)
    min_telemetry_health: float = Field(ge=0.8, le=1.0)


class OptimizationPlanOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "reduce_noise",
        "reduce_bandwidth",
        "reduce_noise_and_bandwidth",
        "improve_battery_life",
        "stabilize_telemetry",
    ]
    target_metric: Literal[
        "accelerometer",
        "temperature",
        "battery",
        "bandwidth",
        "telemetry_health",
    ]
    sampling_rate_hz: float = Field(ge=1, le=20)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    filter: FilterSpecOutput
    telemetry_collection: TelemetryCollectionOutput
    deployment: DeploymentSpecOutput
    rollback: RollbackPolicyOutput
    rationale: str = Field(min_length=1, max_length=500)

