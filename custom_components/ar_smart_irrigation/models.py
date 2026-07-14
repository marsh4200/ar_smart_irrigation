"""Data models for AR Smart Irrigation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .const import (
    DEFAULT_CYCLES,
    DEFAULT_DURATION,
    DEFAULT_SOAK,
    DEFAULT_SOIL_THRESHOLD,
    FREQ_DAILY,
    PHASE_WATERING,
    PROGRAM_DURATION_OVERRIDE,
    PROGRAM_ENABLED,
    PROGRAM_FREQUENCY,
    PROGRAM_ID,
    PROGRAM_INTERVAL,
    PROGRAM_NAME,
    PROGRAM_START_TIMES,
    PROGRAM_WEATHER_ADJUST,
    PROGRAM_WEEKDAYS,
    PROGRAM_ZONES,
    ZONE_AREA,
    ZONE_CYCLES,
    ZONE_DURATION,
    ZONE_ENABLED,
    ZONE_FLOW_RATE,
    ZONE_ID,
    ZONE_NAME,
    ZONE_SOAK,
    ZONE_SOIL_ENTITY,
    ZONE_SOIL_THRESHOLD,
    ZONE_SWITCH,
)


@dataclass
class Zone:
    """A single irrigation zone mapped to a physical switch/valve entity."""

    zone_id: str
    name: str
    switch_entity: str
    default_duration: int = DEFAULT_DURATION
    flow_rate: float | None = None
    area: float | None = None
    soil_moisture_entity: str | None = None
    soil_moisture_threshold: int = DEFAULT_SOIL_THRESHOLD
    cycles: int = DEFAULT_CYCLES
    soak_minutes: int = DEFAULT_SOAK
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Zone":
        return cls(
            zone_id=data[ZONE_ID],
            name=data[ZONE_NAME],
            switch_entity=data[ZONE_SWITCH],
            default_duration=int(data.get(ZONE_DURATION, DEFAULT_DURATION)),
            flow_rate=_opt_float(data.get(ZONE_FLOW_RATE)),
            area=_opt_float(data.get(ZONE_AREA)),
            soil_moisture_entity=data.get(ZONE_SOIL_ENTITY) or None,
            soil_moisture_threshold=int(
                data.get(ZONE_SOIL_THRESHOLD, DEFAULT_SOIL_THRESHOLD)
            ),
            cycles=max(1, int(data.get(ZONE_CYCLES, DEFAULT_CYCLES))),
            soak_minutes=int(data.get(ZONE_SOAK, DEFAULT_SOAK)),
            enabled=bool(data.get(ZONE_ENABLED, True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            ZONE_ID: self.zone_id,
            ZONE_NAME: self.name,
            ZONE_SWITCH: self.switch_entity,
            ZONE_DURATION: self.default_duration,
            ZONE_FLOW_RATE: self.flow_rate,
            ZONE_AREA: self.area,
            ZONE_SOIL_ENTITY: self.soil_moisture_entity,
            ZONE_SOIL_THRESHOLD: self.soil_moisture_threshold,
            ZONE_CYCLES: self.cycles,
            ZONE_SOAK: self.soak_minutes,
            ZONE_ENABLED: self.enabled,
        }

    @property
    def effective_cycles(self) -> int:
        """Cycle-and-soak only makes sense with a soak period."""
        return self.cycles if self.soak_minutes > 0 else 1


@dataclass
class Program:
    """A watering schedule that runs an ordered set of zones."""

    program_id: str
    name: str
    zone_ids: list[str] = field(default_factory=list)
    start_times: list[str] = field(default_factory=list)  # "HH:MM"
    frequency: str = FREQ_DAILY
    weekdays: list[int] = field(default_factory=list)      # 0=Mon..6=Sun
    interval_days: int = 2
    duration_override: int | None = None
    weather_adjust: bool = True
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Program":
        override = data.get(PROGRAM_DURATION_OVERRIDE)
        return cls(
            program_id=data[PROGRAM_ID],
            name=data[PROGRAM_NAME],
            zone_ids=list(data.get(PROGRAM_ZONES, [])),
            start_times=list(data.get(PROGRAM_START_TIMES, [])),
            frequency=data.get(PROGRAM_FREQUENCY, FREQ_DAILY),
            weekdays=[int(d) for d in data.get(PROGRAM_WEEKDAYS, [])],
            interval_days=max(1, int(data.get(PROGRAM_INTERVAL, 2))),
            duration_override=int(override) if override not in (None, "") else None,
            weather_adjust=bool(data.get(PROGRAM_WEATHER_ADJUST, True)),
            enabled=bool(data.get(PROGRAM_ENABLED, True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            PROGRAM_ID: self.program_id,
            PROGRAM_NAME: self.name,
            PROGRAM_ZONES: self.zone_ids,
            PROGRAM_START_TIMES: self.start_times,
            PROGRAM_FREQUENCY: self.frequency,
            PROGRAM_WEEKDAYS: self.weekdays,
            PROGRAM_INTERVAL: self.interval_days,
            PROGRAM_DURATION_OVERRIDE: self.duration_override,
            PROGRAM_WEATHER_ADJUST: self.weather_adjust,
            PROGRAM_ENABLED: self.enabled,
        }


@dataclass
class ZoneStep:
    """A resolved zone execution unit within a run."""

    zone_id: str
    name: str
    switch_entity: str
    cycle_seconds: int          # per-pulse watering time
    cycles: int                 # number of pulses
    soak_seconds: int
    flow_rate: float | None
    litres_used: float = 0.0


@dataclass
class RunState:
    """The live state of the currently executing watering run."""

    source: str                 # program_id, or "manual"
    label: str                  # human readable
    steps: list[ZoneStep]
    step_index: int = 0
    cycle_index: int = 0
    phase: str = PHASE_WATERING
    phase_end: datetime | None = None
    started: datetime | None = None
    uses_master: bool = True

    @property
    def current(self) -> ZoneStep | None:
        if 0 <= self.step_index < len(self.steps):
            return self.steps[self.step_index]
        return None

    @property
    def total_litres(self) -> float:
        return round(sum(s.litres_used for s in self.steps), 1)


def _opt_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
