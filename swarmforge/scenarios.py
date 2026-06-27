from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import Literal


Terrain = Literal["smooth", "muddy", "rocky", "spike_noise"]
NoiseLevel = Literal["low", "medium", "high"]
NetworkProfile = Literal["stable", "jitter", "high_loss"]
BatteryState = Literal["normal", "low", "critical"]
SensorFault = Literal["none", "dropout", "stuck_value"]


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    seed: int
    duration_seconds: int
    baseline_sample_rate_hz: float
    terrain: Terrain
    noise_level: NoiseLevel
    network_profile: NetworkProfile
    battery_state: BatteryState
    sensor_fault: SensorFault
    fleet_size: int

    def to_dict(self) -> dict:
        return asdict(self)


def generate_scenario_matrix(count: int = 50, seed_start: int = 1) -> list[ScenarioSpec]:
    if count < 1:
        raise ValueError("count must be at least 1")

    required = [
        ("muddy", "high", "stable", "normal", "none", 50),
        ("rocky", "high", "jitter", "normal", "none", 50),
        ("muddy", "medium", "high_loss", "low", "none", 50),
        ("smooth", "low", "stable", "low", "dropout", 10),
        ("spike_noise", "high", "jitter", "normal", "none", 100),
    ]
    terrains: list[Terrain] = ["smooth", "muddy", "rocky", "spike_noise"]
    noise_levels: list[NoiseLevel] = ["low", "medium", "high"]
    networks: list[NetworkProfile] = ["stable", "jitter", "high_loss"]
    batteries: list[BatteryState] = ["normal", "low", "critical"]
    faults: list[SensorFault] = ["none", "dropout", "stuck_value"]
    fleet_sizes = [1, 10, 50, 100]

    specs: list[ScenarioSpec] = []
    for index in range(count):
        seed = seed_start + index
        if index < len(required):
            terrain, noise, network, battery, fault, fleet_size = required[index]
        else:
            terrain = terrains[index % len(terrains)]
            noise = noise_levels[(index // len(terrains)) % len(noise_levels)]
            network = networks[(index // 3) % len(networks)]
            battery = batteries[(index // 5) % len(batteries)]
            fault = faults[(index // 7) % len(faults)]
            fleet_size = fleet_sizes[(index // 11) % len(fleet_sizes)]

        specs.append(
            ScenarioSpec(
                scenario_id=_scenario_id(
                    terrain=terrain,
                    noise_level=noise,
                    network_profile=network,
                    battery_state=battery,
                    sensor_fault=fault,
                    seed=seed,
                ),
                seed=seed,
                duration_seconds=30,
                baseline_sample_rate_hz=10,
                terrain=terrain,
                noise_level=noise,
                network_profile=network,
                battery_state=battery,
                sensor_fault=fault,
                fleet_size=fleet_size,
            )
        )

    return specs


def scenario_signal(spec: ScenarioSpec) -> list[float]:
    rng = random.Random(spec.seed)
    sample_count = int(spec.duration_seconds * spec.baseline_sample_rate_hz)
    values: list[float] = []

    terrain_factor = {
        "smooth": 0.2,
        "muddy": 0.7,
        "rocky": 1.0,
        "spike_noise": 0.55,
    }[spec.terrain]
    noise_factor = {
        "low": 0.08,
        "medium": 0.18,
        "high": 0.32,
    }[spec.noise_level]

    for index in range(sample_count):
        t = index / spec.baseline_sample_rate_hz
        base_motion = math.sin(t * 1.2) * 0.8
        jitter = rng.uniform(-noise_factor, noise_factor)
        terrain_noise = 0.0
        if 10 <= t <= 20:
            terrain_noise = rng.uniform(-terrain_factor, terrain_factor)
        spike = 0.0
        if spec.terrain == "spike_noise" and index % 37 == 0:
            spike = rng.choice([-1.3, 1.3])
        values.append(base_motion + jitter + terrain_noise + spike)

    if spec.sensor_fault == "dropout":
        return _apply_dropout(values, rng)
    if spec.sensor_fault == "stuck_value":
        return _apply_stuck_value(values)
    return values


def estimate_telemetry_health(spec: ScenarioSpec) -> float:
    health = 0.995
    if spec.network_profile == "jitter":
        health -= 0.035
    elif spec.network_profile == "high_loss":
        health -= 0.08

    if spec.battery_state == "low":
        health -= 0.025
    elif spec.battery_state == "critical":
        health -= 0.07

    if spec.sensor_fault == "dropout":
        health -= 0.09
    elif spec.sensor_fault == "stuck_value":
        health -= 0.05

    return max(0.0, round(health, 4))


def _scenario_id(
    terrain: str,
    noise_level: str,
    network_profile: str,
    battery_state: str,
    sensor_fault: str,
    seed: int,
) -> str:
    return (
        f"{terrain}_{noise_level}_{network_profile}_"
        f"{battery_state}_{sensor_fault}_seed_{seed}"
    )


def _apply_dropout(values: list[float], rng: random.Random) -> list[float]:
    output = list(values)
    for index in range(0, len(output), 23):
        if index > 0:
            output[index] = output[index - 1] + rng.uniform(-0.01, 0.01)
    return output


def _apply_stuck_value(values: list[float]) -> list[float]:
    output = list(values)
    if not output:
        return output

    start = len(output) // 3
    end = min(len(output), start + 12)
    stuck = output[start]
    for index in range(start, end):
        output[index] = stuck
    return output
