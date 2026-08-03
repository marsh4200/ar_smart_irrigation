"""The watering engine: weather check, then run zones one after another."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any, Callable

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAYS,
    CONF_FREEZE_TEMP,
    CONF_RAIN_THRESHOLD,
    CONF_START_TIME,
    CONF_WEATHER_ENTITY,
    CONF_ZONE_MINUTES,
    CONF_ZONE_SWITCH,
    DAYS,
    DEFAULT_FREEZE_TEMP,
    DEFAULT_MINUTES,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_START_TIME,
    STATUS_DISABLED,
    STATUS_IDLE,
    STATUS_SKIPPED,
    STATUS_WATERING,
    WET_CONDITIONS,
    ZONE_COUNT,
)

_LOGGER = logging.getLogger(__name__)


class IrrigationController:
    """Holds all the state and does the actual watering."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry

        self.enabled: bool = True
        self.status: str = STATUS_IDLE
        self.current_zone: int | None = None
        self.zone_ends_at: datetime | None = None
        self.last_run: datetime | None = None
        self.last_skip_reason: str | None = None

        self._task: asyncio.Task | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    @property
    def cfg(self) -> dict[str, Any]:
        """Options win over the original setup data."""
        return {**self.entry.data, **self.entry.options}

    def zones(self) -> list[tuple[int, str, int]]:
        """Return [(zone_number, switch_entity_id, minutes)] for configured zones."""
        out: list[tuple[int, str, int]] = []
        for i in range(1, ZONE_COUNT + 1):
            ent = self.cfg.get(CONF_ZONE_SWITCH.format(i))
            if not ent:
                continue
            minutes = int(self.cfg.get(CONF_ZONE_MINUTES.format(i), DEFAULT_MINUTES))
            out.append((i, ent, minutes))
        return out

    def zone_entity(self, zone: int) -> str | None:
        return self.cfg.get(CONF_ZONE_SWITCH.format(zone))

    def zone_minutes(self, zone: int) -> int:
        return int(self.cfg.get(CONF_ZONE_MINUTES.format(zone), DEFAULT_MINUTES))

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------
    async def async_setup(self) -> None:
        start = self._start_time()
        self._unsubs.append(
            async_track_time_change(
                self.hass,
                self._scheduled_start,
                hour=start.hour,
                minute=start.minute,
                second=0,
            )
        )
        # Ticks so the "minutes remaining" attribute stays fresh while running.
        self._unsubs.append(
            async_track_time_interval(self.hass, self._tick, timedelta(seconds=30))
        )

    async def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self.async_stop()

    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)

        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    @callback
    def notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    @callback
    def _tick(self, _now) -> None:
        if self.status == STATUS_WATERING:
            self.notify()

    # ------------------------------------------------------------------
    # Schedule
    # ------------------------------------------------------------------
    def _start_time(self) -> time:
        raw = str(self.cfg.get(CONF_START_TIME, DEFAULT_START_TIME))
        try:
            parts = [int(p) for p in raw.split(":")]
            while len(parts) < 3:
                parts.append(0)
            return time(parts[0], parts[1], parts[2])
        except (ValueError, IndexError):
            return time(6, 0, 0)

    def _active_days(self) -> list[str]:
        days = self.cfg.get(CONF_DAYS) or DAYS
        if isinstance(days, str):
            days = [days]
        return [d for d in days if d in DAYS]

    @property
    def next_run(self) -> datetime | None:
        """Next scheduled start, or None if the program is off."""
        if not self.enabled:
            return None
        active = self._active_days()
        if not active or not self.zones():
            return None

        start = self._start_time()
        now = dt_util.now()
        for offset in range(0, 8):
            day = now + timedelta(days=offset)
            if DAYS[day.weekday()] not in active:
                continue
            candidate = day.replace(
                hour=start.hour, minute=start.minute, second=0, microsecond=0
            )
            if candidate > now:
                return candidate
        return None

    async def _scheduled_start(self, _now) -> None:
        if not self.enabled:
            _LOGGER.debug("Program disabled, skipping scheduled run")
            return
        if DAYS[dt_util.now().weekday()] not in self._active_days():
            return

        ok, reason = await self.async_check_weather()
        if not ok:
            self.status = STATUS_SKIPPED
            self.last_skip_reason = reason
            self.notify()
            _LOGGER.info("Skipping watering: %s", reason)
            return

        await self.async_run([z[0] for z in self.zones()])

    # ------------------------------------------------------------------
    # Weather
    # ------------------------------------------------------------------
    async def async_check_weather(self) -> tuple[bool, str | None]:
        """Return (ok_to_water, reason_if_not)."""
        entity_id = self.cfg.get(CONF_WEATHER_ENTITY)
        if not entity_id:
            return True, None

        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            _LOGGER.debug("Weather entity %s not usable, watering anyway", entity_id)
            return True, None

        # 1. Is it wet right now?
        if state.state in WET_CONDITIONS:
            return False, f"currently {state.state}"

        # 2. Is it freezing?
        freeze = float(self.cfg.get(CONF_FREEZE_TEMP, DEFAULT_FREEZE_TEMP))
        temp = state.attributes.get("temperature")
        if temp is not None:
            try:
                if float(temp) < freeze:
                    return False, f"too cold ({temp}°)"
            except (TypeError, ValueError):
                pass

        # 3. Is meaningful rain forecast for today?
        threshold = float(self.cfg.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD))
        if threshold > 0:
            rain = await self._forecast_rain(entity_id)
            if rain is not None and rain >= threshold:
                return False, f"{rain}mm rain forecast"

        return True, None

    async def _forecast_rain(self, entity_id: str) -> float | None:
        """Today's forecast precipitation in mm, or None if unavailable."""
        try:
            result = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "daily"},
                target={ATTR_ENTITY_ID: entity_id},
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - forecasts are best-effort
            _LOGGER.debug("Could not fetch forecast for %s: %s", entity_id, err)
            return None

        forecast = (result or {}).get(entity_id, {}).get("forecast") or []
        if not forecast:
            return None
        value = forecast[0].get("precipitation")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    async def async_run(self, zones: list[int] | None = None, *, check_weather: bool = False) -> None:
        """Run the given zones in sequence. None means all configured zones."""
        if zones is None:
            zones = [z[0] for z in self.zones()]
        zones = [z for z in zones if self.zone_entity(z)]
        if not zones:
            _LOGGER.warning("No zones configured to run")
            return

        if check_weather:
            ok, reason = await self.async_check_weather()
            if not ok:
                self.status = STATUS_SKIPPED
                self.last_skip_reason = reason
                self.notify()
                _LOGGER.info("Skipping watering: %s", reason)
                return

        await self.async_stop()
        self._task = self.entry.async_create_background_task(
            self.hass, self._runner(zones), f"{self.entry.entry_id}_run"
        )

    async def _runner(self, zones: list[int]) -> None:
        self.last_skip_reason = None
        try:
            for zone in zones:
                entity_id = self.zone_entity(zone)
                if not entity_id:
                    continue
                minutes = self.zone_minutes(zone)

                self.status = STATUS_WATERING
                self.current_zone = zone
                self.zone_ends_at = dt_util.utcnow() + timedelta(minutes=minutes)
                self.notify()

                await self._switch(entity_id, True)
                _LOGGER.info("Zone %s on for %s minutes", zone, minutes)
                try:
                    await asyncio.sleep(minutes * 60)
                finally:
                    await self._switch(entity_id, False)

            self.last_run = dt_util.utcnow()
        except asyncio.CancelledError:
            _LOGGER.info("Watering cancelled")
            raise
        finally:
            await self._all_off()
            self.current_zone = None
            self.zone_ends_at = None
            if self.status == STATUS_WATERING:
                self.status = STATUS_IDLE if self.enabled else STATUS_DISABLED
            self.notify()

    async def async_stop(self) -> None:
        """Cancel any run and shut every relay off."""
        task, self._task = self._task, None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._all_off()
        self.current_zone = None
        self.zone_ends_at = None
        if self.status == STATUS_WATERING:
            self.status = STATUS_IDLE
        self.notify()

    async def _all_off(self) -> None:
        for _zone, entity_id, _minutes in self.zones():
            await self._switch(entity_id, False)

    async def _switch(self, entity_id: str, on: bool) -> None:
        domain = entity_id.split(".")[0]
        if domain == "valve":
            service = "open_valve" if on else "close_valve"
            call_domain = "valve"
        else:
            service = "turn_on" if on else "turn_off"
            call_domain = "homeassistant"
        # Shielded so that a cancelled run still gets its relays switched off.
        try:
            await asyncio.shield(
                self.hass.services.async_call(
                    call_domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to switch %s: %s", entity_id, err)

    # ------------------------------------------------------------------
    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.status = STATUS_DISABLED
            self.hass.async_create_task(self.async_stop())
        elif self.status == STATUS_DISABLED:
            self.status = STATUS_IDLE
        self.notify()
