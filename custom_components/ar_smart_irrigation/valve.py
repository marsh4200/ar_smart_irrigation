"""Valve entities — one per irrigation zone."""

from __future__ import annotations

from homeassistant.components.valve import (
    ValveEntity,
    ValveEntityFeature,
    ValveDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ARSmartIrrigationCoordinator
from .entity import ARIrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a valve entity for each configured zone."""
    coordinator: ARSmartIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZoneValve(coordinator, zone.zone_id, zone.name) for zone in coordinator.zones
    )


class ZoneValve(ARIrrigationEntity, ValveEntity):
    """Represents a watering zone as an openable valve.

    Opening the valve starts a manual run of the zone for its default
    duration; closing it stops all watering. Because valves are driven by the
    engine (sequencing, cycle-and-soak) the state is *reported*, not directly
    positioned, so this is a non-positional valve.
    """

    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(
        self, coordinator: ARSmartIrrigationCoordinator, zone_id: str, name: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_zone_{zone_id}"

    @property
    def is_closed(self) -> bool:
        run = self.coordinator.active_run
        if run and run.current and run.current.zone_id == self._zone_id:
            return run.phase != "watering"
        return True

    @property
    def extra_state_attributes(self) -> dict:
        zone = self.coordinator.get_zone(self._zone_id)
        if not zone:
            return {}
        run = self.coordinator.active_run
        active = bool(run and run.current and run.current.zone_id == self._zone_id)
        attrs = {
            "backing_entity": zone.switch_entity,
            "default_duration_min": zone.default_duration,
            "flow_rate_lpm": zone.flow_rate,
            "cycles": zone.cycles,
            "soak_minutes": zone.soak_minutes,
            "enabled": zone.enabled,
            "active": active,
        }
        if active and run and run.current:
            attrs["litres_this_run"] = round(run.current.litres_used, 1)
            attrs["remaining_seconds"] = self.coordinator.data.get("remaining_seconds")
        return attrs

    async def async_open_valve(self) -> None:
        await self.coordinator.async_start_zone(self._zone_id)

    async def async_close_valve(self) -> None:
        await self.coordinator.async_stop_zone(self._zone_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
