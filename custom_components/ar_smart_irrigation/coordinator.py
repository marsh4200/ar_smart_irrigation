"""Coordinator and watering engine for AR Smart Irrigation.

The coordinator owns all runtime state and drives watering from a periodic
tick. It is intentionally the single source of truth: entities are thin views
over ``coordinator.data`` and every mutation flows back through here so the UI,
persistence and physical valves stay consistent.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ET_ADJUST,
    CONF_ET_BASE_TEMP,
    CONF_FLOW_HIGH_FACTOR,
    CONF_FLOW_LEAK_DETECTION,
    CONF_FLOW_LOW_FACTOR,
    CONF_FLOW_SENSOR,
    CONF_FREEZE_SKIP,
    CONF_FREEZE_THRESHOLD,
    CONF_MASTER_LEAD,
    CONF_MASTER_VALVE,
    CONF_PROGRAMS,
    CONF_PUMP_ENTITY,
    CONF_RAIN_SKIP,
    CONF_RAIN_THRESHOLD,
    CONF_WEATHER_ENTITY,
    CONF_WIND_SKIP,
    CONF_WIND_THRESHOLD,
    CONF_ZONES,
    DEFAULT_ET_BASE_TEMP,
    DEFAULT_FLOW_HIGH_FACTOR,
    DEFAULT_FLOW_LOW_FACTOR,
    DEFAULT_FREEZE_THRESHOLD,
    DEFAULT_MASTER_LEAD,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_SEASONAL,
    DEFAULT_WIND_THRESHOLD,
    DOMAIN,
    ENGINE_TICK,
    FLOW_ANOMALY_TICKS,
    FREQ_DAILY,
    FREQ_EVEN,
    FREQ_INTERVAL,
    FREQ_ODD,
    FREQ_WEEKDAYS,
    PHASE_SOAKING,
    PHASE_WATERING,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import Program, RunState, Zone, ZoneStep
from .weather import evaluate_weather

_LOGGER = logging.getLogger(__name__)

_EPOCH = date(2000, 1, 1)


class ARSmartIrrigationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Owns irrigation state and runs the watering engine."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # we push updates ourselves from the tick
        )
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._unsub_tick = None

        # Persisted runtime state
        self.system_enabled: bool = True
        self.seasonal_adjust: int = DEFAULT_SEASONAL
        self.rain_delay_until: datetime | None = None
        self.program_enabled: dict[str, bool] = {}
        self._water_used_today: float = 0.0
        self._water_day: date = dt_util.now().date()

        # Live (non-persisted) state
        self.active_run: RunState | None = None
        self.queue: list[RunState] = []
        self._fired: set[tuple[str, str, str]] = set()  # (prog, HH:MM, iso-date)
        self.skip_reasons: list[str] = []
        self.flow_anomaly: str | None = None
        self._flow_bad_ticks = 0
        self.next_run: datetime | None = None

    # ------------------------------------------------------------------ setup
    async def async_init(self) -> None:
        """Load persisted state and start the engine tick."""
        stored = await self._store.async_load() or {}
        self.system_enabled = stored.get("system_enabled", True)
        self.seasonal_adjust = int(stored.get("seasonal_adjust", DEFAULT_SEASONAL))
        self.program_enabled = dict(stored.get("program_enabled", {}))
        rd = stored.get("rain_delay_until")
        self.rain_delay_until = dt_util.parse_datetime(rd) if rd else None
        self._water_used_today = float(stored.get("water_used_today", 0.0))
        wd = stored.get("water_day")
        self._water_day = date.fromisoformat(wd) if wd else dt_util.now().date()

        self._unsub_tick = async_track_time_interval(
            self.hass, self._async_tick, ENGINE_TICK
        )
        self._recalc_next_run()
        self._push()

    async def async_shutdown(self) -> None:
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None
        await self._async_stop_all(save=False)
        await self._save()

    async def _save(self) -> None:
        await self._store.async_save(
            {
                "system_enabled": self.system_enabled,
                "seasonal_adjust": self.seasonal_adjust,
                "program_enabled": self.program_enabled,
                "rain_delay_until": self.rain_delay_until.isoformat()
                if self.rain_delay_until
                else None,
                "water_used_today": round(self._water_used_today, 2),
                "water_day": self._water_day.isoformat(),
            }
        )

    # -------------------------------------------------------------- config views
    @property
    def _opt(self) -> dict[str, Any]:
        """Merged config: options override initial data."""
        merged = dict(self.entry.data)
        merged.update(self.entry.options)
        return merged

    @property
    def zones(self) -> list[Zone]:
        return [Zone.from_dict(z) for z in self._opt.get(CONF_ZONES, [])]

    @property
    def programs(self) -> list[Program]:
        return [Program.from_dict(p) for p in self._opt.get(CONF_PROGRAMS, [])]

    def get_zone(self, zone_id: str) -> Zone | None:
        return next((z for z in self.zones if z.zone_id == zone_id), None)

    def get_program(self, program_id: str) -> Program | None:
        return next((p for p in self.programs if p.program_id == program_id), None)

    def is_program_enabled(self, program_id: str) -> bool:
        return self.program_enabled.get(program_id, True)

    # ---------------------------------------------------------------- the tick
    async def _async_tick(self, now: datetime) -> None:
        try:
            await self._roll_day()
            await self._check_schedules()
            await self._advance_run()
            await self._start_queued()
            self._monitor_flow()
            self._recalc_next_run()
        except Exception:  # noqa: BLE001 - never let the tick die silently
            _LOGGER.exception("Irrigation engine tick failed")
        self._push()

    async def _roll_day(self) -> None:
        today = dt_util.now().date()
        if today != self._water_day:
            self._water_day = today
            self._water_used_today = 0.0
            # prune stale "fired" markers
            iso = today.isoformat()
            self._fired = {f for f in self._fired if f[2] == iso}
            await self._save()

    # ----------------------------------------------------------- scheduling
    async def _check_schedules(self) -> None:
        if not self.system_enabled or self._rain_delayed():
            return
        now = dt_util.now()
        hhmm = now.strftime("%H:%M")
        iso = now.date().isoformat()

        for program in self.programs:
            if not program.enabled or not self.is_program_enabled(program.program_id):
                continue
            if hhmm not in program.start_times:
                continue
            key = (program.program_id, hhmm, iso)
            if key in self._fired:
                continue
            if not self._day_matches(program, now):
                continue
            self._fired.add(key)

            decision = await self._weather_for(program)
            if decision.skip:
                self.skip_reasons = decision.reasons
                _LOGGER.info(
                    "Program '%s' skipped: %s",
                    program.name,
                    "; ".join(decision.reasons),
                )
                continue
            run = self._build_run(program, decision.factor)
            if run.steps:
                self.queue.append(run)
                _LOGGER.info("Program '%s' queued (%d zones)", program.name, len(run.steps))

    def _day_matches(self, program: Program, now: datetime) -> bool:
        freq = program.frequency
        if freq == FREQ_DAILY:
            return True
        if freq == FREQ_WEEKDAYS:
            return now.weekday() in program.weekdays
        if freq == FREQ_EVEN:
            return now.day % 2 == 0
        if freq == FREQ_ODD:
            return now.day % 2 == 1
        if freq == FREQ_INTERVAL:
            delta = (now.date() - _EPOCH).days
            return delta % max(1, program.interval_days) == 0
        return True

    async def _weather_for(self, program: Program):
        opt = self._opt
        if not program.weather_adjust:
            from .weather import WeatherDecision

            return WeatherDecision()
        return await evaluate_weather(
            self.hass,
            weather_entity=opt.get(CONF_WEATHER_ENTITY),
            et_enabled=opt.get(CONF_ET_ADJUST, True),
            et_base_temp=float(opt.get(CONF_ET_BASE_TEMP, DEFAULT_ET_BASE_TEMP)),
            rain_skip=opt.get(CONF_RAIN_SKIP, True),
            rain_threshold=float(opt.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD)),
            freeze_skip=opt.get(CONF_FREEZE_SKIP, True),
            freeze_threshold=float(
                opt.get(CONF_FREEZE_THRESHOLD, DEFAULT_FREEZE_THRESHOLD)
            ),
            wind_skip=opt.get(CONF_WIND_SKIP, False),
            wind_threshold=float(opt.get(CONF_WIND_THRESHOLD, DEFAULT_WIND_THRESHOLD)),
        )

    def _build_run(self, program: Program, weather_factor: float) -> RunState:
        steps: list[ZoneStep] = []
        multiplier = (self.seasonal_adjust / 100.0) * weather_factor
        # Preserve the zone order as defined in options, filtered to the program.
        selected = [z for z in self.zones if z.zone_id in program.zone_ids]
        for zone in selected:
            if not zone.enabled:
                continue
            if self._soil_too_wet(zone):
                _LOGGER.info("Zone '%s' skipped: soil moisture above threshold", zone.name)
                continue
            base = program.duration_override or zone.default_duration
            total_seconds = int(round(base * 60 * multiplier))
            if total_seconds <= 0:
                continue
            cycles = zone.effective_cycles
            steps.append(
                ZoneStep(
                    zone_id=zone.zone_id,
                    name=zone.name,
                    switch_entity=zone.switch_entity,
                    cycle_seconds=max(1, total_seconds // cycles),
                    cycles=cycles,
                    soak_seconds=zone.soak_minutes * 60,
                    flow_rate=zone.flow_rate,
                )
            )
        return RunState(source=program.program_id, label=program.name, steps=steps)

    def _soil_too_wet(self, zone: Zone) -> bool:
        if not zone.soil_moisture_entity:
            return False
        state = self.hass.states.get(zone.soil_moisture_entity)
        if state is None or state.state in ("unknown", "unavailable"):
            return False
        try:
            return float(state.state) >= zone.soil_moisture_threshold
        except (TypeError, ValueError):
            return False

    # ------------------------------------------------------------- run engine
    async def _start_queued(self) -> None:
        if self.active_run is not None or not self.queue:
            return
        if not self.system_enabled or self._rain_delayed():
            self.queue.clear()
            return
        self.active_run = self.queue.pop(0)
        await self._begin_run(self.active_run)

    async def _begin_run(self, run: RunState) -> None:
        run.started = dt_util.utcnow()
        self.skip_reasons = []
        if run.uses_master:
            await self._set_master(True)
            lead = int(self._opt.get(CONF_MASTER_LEAD, DEFAULT_MASTER_LEAD))
            if lead > 0:
                # Give the master valve/pump a head start before the first zone.
                run.phase = PHASE_SOAKING
                run.phase_end = dt_util.utcnow() + timedelta(seconds=lead)
                return
        await self._start_step(run)

    async def _start_step(self, run: RunState) -> None:
        step = run.current
        if step is None:
            await self._finish_run(run)
            return
        run.phase = PHASE_WATERING
        run.phase_end = dt_util.utcnow() + timedelta(seconds=step.cycle_seconds)
        await self._set_entity(step.switch_entity, True)
        _LOGGER.debug(
            "Watering zone '%s' cycle %d/%d for %ds",
            step.name,
            run.cycle_index + 1,
            step.cycles,
            step.cycle_seconds,
        )

    async def _advance_run(self) -> None:
        run = self.active_run
        if run is None or run.phase_end is None:
            return
        now = dt_util.utcnow()
        if now < run.phase_end:
            # accrue water estimate for the elapsed slice while watering
            if run.phase == PHASE_WATERING:
                self._accrue_water(run, ENGINE_TICK.total_seconds())
            return

        if run.phase == PHASE_SOAKING and run.step_index == 0 and run.cycle_index == 0:
            # This was the master-lead delay, not a real soak.
            await self._start_step(run)
            return

        if run.phase == PHASE_WATERING:
            step = run.current
            if step is None:
                await self._finish_run(run)
                return
            self._accrue_water(run, run_remainder_seconds(run, now))
            await self._set_entity(step.switch_entity, False)
            run.cycle_index += 1
            if run.cycle_index < step.cycles:
                # more pulses to go — soak first
                run.phase = PHASE_SOAKING
                run.phase_end = now + timedelta(seconds=step.soak_seconds)
            else:
                await self._next_step(run)
        elif run.phase == PHASE_SOAKING:
            step = run.current
            if step is None:
                await self._finish_run(run)
                return
            run.phase = PHASE_WATERING
            run.phase_end = now + timedelta(seconds=step.cycle_seconds)
            await self._set_entity(step.switch_entity, True)

    async def _next_step(self, run: RunState) -> None:
        run.step_index += 1
        run.cycle_index = 0
        if run.current is None:
            await self._finish_run(run)
        else:
            await self._start_step(run)

    async def _finish_run(self, run: RunState) -> None:
        if run.current:
            await self._set_entity(run.current.switch_entity, False)
        if run.uses_master:
            await self._set_master(False)
        self._water_used_today += run.total_litres
        _LOGGER.info("Run '%s' complete — %.1f L used", run.label, run.total_litres)
        if self.active_run is run:
            self.active_run = None
        await self._save()

    def _accrue_water(self, run: RunState, seconds: float) -> None:
        step = run.current
        if step is None or step.flow_rate is None:
            return
        step.litres_used += step.flow_rate * (max(0.0, seconds) / 60.0)

    # -------------------------------------------------------------- flow watch
    def _monitor_flow(self) -> None:
        opt = self._opt
        sensor = opt.get(CONF_FLOW_SENSOR)
        if not sensor or not opt.get(CONF_FLOW_LEAK_DETECTION, False):
            self.flow_anomaly = None
            self._flow_bad_ticks = 0
            return

        state = self.hass.states.get(sensor)
        actual = None
        if state and state.state not in ("unknown", "unavailable"):
            try:
                actual = float(state.state)
            except (TypeError, ValueError):
                actual = None

        run = self.active_run
        watering = run is not None and run.phase == PHASE_WATERING
        expected = 0.0
        if watering and run.current and run.current.flow_rate:
            expected = run.current.flow_rate

        high = float(opt.get(CONF_FLOW_HIGH_FACTOR, DEFAULT_FLOW_HIGH_FACTOR))
        low = float(opt.get(CONF_FLOW_LOW_FACTOR, DEFAULT_FLOW_LOW_FACTOR))

        anomaly: str | None = None
        if actual is not None:
            if not watering and actual > 0.5:
                anomaly = "unexpected_flow"  # valves closed but water is moving
            elif watering and expected > 0:
                if actual > expected * high:
                    anomaly = "high_flow"    # burst pipe / stuck valve
                elif actual < expected * low:
                    anomaly = "low_flow"     # clog / no pressure

        if anomaly:
            self._flow_bad_ticks += 1
            if self._flow_bad_ticks >= FLOW_ANOMALY_TICKS:
                if self.flow_anomaly != anomaly:
                    _LOGGER.warning("Flow anomaly detected: %s", anomaly)
                self.flow_anomaly = anomaly
        else:
            self._flow_bad_ticks = 0
            self.flow_anomaly = None

    # --------------------------------------------------------- entity helpers
    async def _set_entity(self, entity_id: str | None, turn_on: bool) -> None:
        if not entity_id:
            return
        domain = entity_id.split(".")[0]
        if domain == "valve":
            service = "open_valve" if turn_on else "close_valve"
            await self.hass.services.async_call(
                "valve", service, {ATTR_ENTITY_ID: entity_id}, blocking=False
            )
        else:
            service = "turn_on" if turn_on else "turn_off"
            await self.hass.services.async_call(
                "homeassistant", service, {ATTR_ENTITY_ID: entity_id}, blocking=False
            )

    async def _set_master(self, turn_on: bool) -> None:
        opt = self._opt
        for key in (CONF_MASTER_VALVE, CONF_PUMP_ENTITY):
            await self._set_entity(opt.get(key), turn_on)

    def _rain_delayed(self) -> bool:
        return bool(self.rain_delay_until and dt_util.utcnow() < self.rain_delay_until)

    # ------------------------------------------------------------- public API
    async def async_start_zone(
        self, zone_id: str, duration_min: int | None = None
    ) -> None:
        zone = self.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Unknown zone: {zone_id}")
        minutes = duration_min or zone.default_duration
        step = ZoneStep(
            zone_id=zone.zone_id,
            name=zone.name,
            switch_entity=zone.switch_entity,
            cycle_seconds=max(1, int(minutes * 60)),
            cycles=1,
            soak_seconds=0,
            flow_rate=zone.flow_rate,
        )
        run = RunState(source="manual", label=f"Manual: {zone.name}", steps=[step])
        # Manual runs jump the queue and replace any active run.
        if self.active_run:
            await self._async_stop_all(save=False)
        self.active_run = run
        await self._begin_run(run)
        self._push()

    async def async_stop_zone(self, zone_id: str) -> None:
        run = self.active_run
        if run and run.current and run.current.zone_id == zone_id:
            await self.async_stop_all()
        else:
            zone = self.get_zone(zone_id)
            if zone:
                await self._set_entity(zone.switch_entity, False)
        self._push()

    async def async_stop_all(self) -> None:
        await self._async_stop_all(save=True)
        self._push()

    async def _async_stop_all(self, save: bool) -> None:
        for zone in self.zones:
            await self._set_entity(zone.switch_entity, False)
        await self._set_master(False)
        self.active_run = None
        self.queue.clear()
        if save:
            await self._save()

    async def async_run_program(self, program_id: str) -> None:
        program = self.get_program(program_id)
        if program is None:
            raise ValueError(f"Unknown program: {program_id}")
        decision = await self._weather_for(program)
        run = self._build_run(program, decision.factor)
        if not run.steps:
            _LOGGER.warning("Program '%s' produced no zones to run", program.name)
            return
        run.label = f"Manual: {program.name}"
        self.queue.append(run)
        self._push()

    async def async_skip_next(self) -> None:
        if self.active_run:
            await self.async_stop_all()
        elif self.queue:
            self.queue.pop(0)
        self._push()

    async def async_rain_delay(self, days: int) -> None:
        if days <= 0:
            self.rain_delay_until = None
        else:
            self.rain_delay_until = dt_util.utcnow() + timedelta(days=days)
        await self._save()
        self._push()

    async def async_set_seasonal(self, percent: int) -> None:
        self.seasonal_adjust = max(0, min(200, int(percent)))
        await self._save()
        self._push()

    async def async_set_system_enabled(self, enabled: bool) -> None:
        self.system_enabled = enabled
        if not enabled:
            await self._async_stop_all(save=False)
        await self._save()
        self._push()

    async def async_set_program_enabled(self, program_id: str, enabled: bool) -> None:
        self.program_enabled[program_id] = enabled
        await self._save()
        self._push()

    # ---------------------------------------------------------- next-run calc
    def _recalc_next_run(self) -> None:
        now = dt_util.now()
        best: datetime | None = None
        for program in self.programs:
            if not program.enabled or not self.is_program_enabled(program.program_id):
                continue
            for start in program.start_times:
                candidate = self._next_occurrence(program, start, now)
                if candidate and (best is None or candidate < best):
                    best = candidate
        self.next_run = best

    def _next_occurrence(
        self, program: Program, start: str, now: datetime
    ) -> datetime | None:
        try:
            hh, mm = (int(x) for x in start.split(":"))
        except ValueError:
            return None
        for offset in range(0, 14):
            day = now.date() + timedelta(days=offset)
            probe = now.replace(
                year=day.year, month=day.month, day=day.day,
                hour=hh, minute=mm, second=0, microsecond=0,
            )
            if probe <= now:
                continue
            if self._day_matches(program, probe):
                return probe
        return None

    # -------------------------------------------------------------- snapshot
    @callback
    def _push(self) -> None:
        run = self.active_run
        current = run.current if run else None
        remaining = 0
        if run and run.phase_end:
            remaining = max(0, int((run.phase_end - dt_util.utcnow()).total_seconds()))

        self.async_set_updated_data(
            {
                "system_enabled": self.system_enabled,
                "watering": run is not None,
                "active_program": run.label if run else None,
                "active_zone": current.name if current else None,
                "phase": run.phase if run else None,
                "remaining_seconds": remaining,
                "queue_depth": len(self.queue),
                "seasonal_adjust": self.seasonal_adjust,
                "rain_delay_until": self.rain_delay_until,
                "rain_delayed": self._rain_delayed(),
                "next_run": self.next_run,
                "water_used_today": round(self._water_used_today, 1),
                "run_litres": run.total_litres if run else 0.0,
                "skip_reasons": list(self.skip_reasons),
                "flow_anomaly": self.flow_anomaly,
            }
        )


def run_remainder_seconds(run: RunState, now: datetime) -> float:
    """Seconds of the current watering slice that had not yet been accrued."""
    if run.phase_end is None:
        return 0.0
    return max(0.0, ENGINE_TICK.total_seconds() - max(0.0, (run.phase_end - now).total_seconds()))
