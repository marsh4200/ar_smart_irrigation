"""Sensors: what it's doing now, and when it runs next."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    STATUS_DISABLED,
    STATUS_IDLE,
    STATUS_SKIPPED,
    STATUS_WATERING,
)
from .controller import IrrigationController
from .entity import IrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StatusSensor(controller), NextRunSensor(controller)])


class StatusSensor(IrrigationEntity, SensorEntity):
    """Idle / watering / skipped / disabled."""

    _attr_name = "Status"
    _attr_icon = "mdi:water-pump"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATUS_IDLE, STATUS_WATERING, STATUS_SKIPPED, STATUS_DISABLED]
    _attr_translation_key = "status"

    def __init__(self, controller: IrrigationController) -> None:
        super().__init__(controller, "status")

    @property
    def native_value(self) -> str:
        return self.controller.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        remaining = None
        if self.controller.zone_ends_at:
            secs = (self.controller.zone_ends_at - dt_util.utcnow()).total_seconds()
            remaining = max(0, round(secs / 60, 1))
        zone_name = (
            self.controller.zone_name(self.controller.current_zone)
            if self.controller.current_zone
            else None
        )
        return {
            "current_zone": zone_name,
            "current_program": self.controller.current_program_name,
            "minutes_remaining": remaining,
            "last_run": self.controller.last_run,
            "last_skip_reason": self.controller.last_skip_reason,
            "skip_today": self.controller.skip_today,
            "zones_configured": len(self.controller.zones()),
            "programs_configured": len(self.controller.programs()),
        }


class NextRunSensor(IrrigationEntity, SensorEntity):
    """Next scheduled start time, across every enabled program."""

    _attr_name = "Next run"
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: IrrigationController) -> None:
        super().__init__(controller, "next_run")

    @property
    def native_value(self) -> datetime | None:
        return self.controller.next_run
