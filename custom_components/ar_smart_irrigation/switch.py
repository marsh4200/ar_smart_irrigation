"""Switches: the program master, plus one run switch per configured zone."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .controller import IrrigationController
from .entity import IrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [ProgramSwitch(controller)]
    for zone, _entity_id, _minutes in controller.zones():
        entities.append(ZoneSwitch(controller, zone))
    async_add_entities(entities)


class ProgramSwitch(IrrigationEntity, SwitchEntity, RestoreEntity):
    """Turn the whole schedule on or off."""

    _attr_name = "Program"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, controller: IrrigationController) -> None:
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


class ZoneSwitch(IrrigationEntity, SwitchEntity):
    """Turn a single zone on for its configured runtime."""

    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, controller: IrrigationController, zone: int) -> None:
        super().__init__(controller, f"zone_{zone}")
        self._zone = zone
        self._attr_name = f"Zone {zone}"

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
