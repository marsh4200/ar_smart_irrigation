"""Button entities for one-shot actions."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ARSmartIrrigationCoordinator
from .entity import ARIrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ARSmartIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StopAllButton(coordinator), SkipNextButton(coordinator)])


class StopAllButton(ARIrrigationEntity, ButtonEntity):
    """Immediately stop watering and clear the queue."""

    _attr_name = "Stop all"
    _attr_icon = "mdi:stop-circle"

    def __init__(self, coordinator: ARSmartIrrigationCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_stop_all"

    async def async_press(self) -> None:
        await self.coordinator.async_stop_all()


class SkipNextButton(ARIrrigationEntity, ButtonEntity):
    """Skip the currently active or next queued run."""

    _attr_name = "Skip current/next"
    _attr_icon = "mdi:skip-next-circle"

    def __init__(self, coordinator: ARSmartIrrigationCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_skip_next"

    async def async_press(self) -> None:
        await self.coordinator.async_skip_next()
