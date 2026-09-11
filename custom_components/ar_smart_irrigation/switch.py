"""Switches: whole-system enable, skip-today, per-program enable, and one run
switch per configured zone.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .controller import IrrigationController
from .entity import IrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [SystemSwitch(controller), SkipTodaySwitch(controller)]
    for program in controller.programs():
        entities.append(ProgramEnableSwitch(controller, program.id, program.name))
    for zone, _entity_id, _minutes, name in controller.zones():
        entities.append(ZoneSwitch(controller, zone, name))
    async_add_entities(entities)


class SystemSwitch(IrrigationEntity, SwitchEntity, RestoreEntity):
    """Master enable for the whole system. Off = nothing runs, ever."""

    _attr_name = "System"
    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, controller: IrrigationController) -> None:
        # Unique id kept as "program" so upgrading installs don't get a new entity.
        super().__init__(controller, "program")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self.controller.set_enabled(last.state == "on")

    @property
    def is_on(self) -> bool:
        return self.controller.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.controller.set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.controller.set_enabled(False)


class SkipTodaySwitch(IrrigationEntity, SwitchEntity, RestoreEntity):
    """Cancel today's scheduled run(s) only. Clears itself at midnight."""

    _attr_name = "Skip today"
    _attr_icon = "mdi:calendar-remove"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: IrrigationController) -> None:
        super().__init__(controller, "skip_today")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        # Only honour a restored "on" if it was set today — otherwise it's a
        # stale armed-skip from a previous day and should not carry over.
        if last is not None and last.state == "on" and last.last_changed.date() == dt_util.now().date():
            self.controller.set_skip_today(True)

    @property
    def is_on(self) -> bool:
        return self.controller.skip_today

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.controller.set_skip_today(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.controller.set_skip_today(False)


class ProgramEnableSwitch(IrrigationEntity, SwitchEntity, RestoreEntity):
    """Enable or disable a single program without touching the others."""

    _attr_icon = "mdi:calendar-clock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: IrrigationController, program_id: int, name: str) -> None:
        super().__init__(controller, f"program_{program_id}_enabled")
        self._program_id = program_id
        self._attr_name = f"{name} enabled"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self.controller.set_program_enabled(self._program_id, last.state == "on")

    @property
    def is_on(self) -> bool:
        return self.controller.is_program_enabled(self._program_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.controller.set_program_enabled(self._program_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.controller.set_program_enabled(self._program_id, False)


class ZoneSwitch(IrrigationEntity, SwitchEntity):
    """Turn a single zone on for its configured runtime."""

    _attr_icon = "mdi:water"

    def __init__(self, controller: IrrigationController, zone: int, name: str) -> None:
        super().__init__(controller, f"zone_{zone}")
        self._zone = zone
        self._attr_name = name

    @property
    def is_on(self) -> bool:
        return self.controller.current_zone == self._zone

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "relay": self.controller.zone_entity(self._zone),
            "runtime_minutes": self.controller.zone_minutes(self._zone),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_run([self._zone])

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_stop()
