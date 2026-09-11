"""Binary sensors: quick automation triggers for watering and weather skips."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STATUS_SKIPPED, STATUS_WATERING
from .controller import IrrigationController
from .entity import IrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WateringBinarySensor(controller), WeatherSkipBinarySensor(controller)])


class WateringBinarySensor(IrrigationEntity, BinarySensorEntity):
    """On while any zone is actively watering."""

    _attr_name = "Watering"
    _attr_icon = "mdi:sprinkler-variant"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, controller: IrrigationController) -> None:
        super().__init__(controller, "watering")

    @property
    def is_on(self) -> bool:
        return self.controller.status == STATUS_WATERING


class WeatherSkipBinarySensor(IrrigationEntity, BinarySensorEntity):
    """On when the most recent scheduled run was skipped (weather, or skip-today)."""

    _attr_name = "Last run skipped"
    _attr_icon = "mdi:weather-pouring"

    def __init__(self, controller: IrrigationController) -> None:
        super().__init__(controller, "last_run_skipped")

    @property
    def is_on(self) -> bool:
        return self.controller.status == STATUS_SKIPPED

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"reason": self.controller.last_skip_reason}
