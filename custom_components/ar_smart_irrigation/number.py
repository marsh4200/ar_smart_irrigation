"""Number entities for live tuning: seasonal budget and rain delay."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import ARSmartIrrigationCoordinator
from .entity import ARIrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ARSmartIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [SeasonalAdjustNumber(coordinator), RainDelayNumber(coordinator)]
    )


class SeasonalAdjustNumber(ARIrrigationEntity, NumberEntity):
    """Global watering budget as a percentage of configured durations."""

    _attr_name = "Seasonal adjustment"
    _attr_icon = "mdi:sun-thermometer"
    _attr_native_min_value = 0
    _attr_native_max_value = 200
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: ARSmartIrrigationCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_seasonal_number"

    @property
    def native_value(self) -> float:
        return self.coordinator.seasonal_adjust

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_seasonal(int(value))

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class RainDelayNumber(ARIrrigationEntity, NumberEntity):
    """Days to suspend all automatic watering. 0 clears the delay."""

    _attr_name = "Rain delay"
    _attr_icon = "mdi:weather-rainy"
    _attr_native_min_value = 0
    _attr_native_max_value = 14
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "d"
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ARSmartIrrigationCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_rain_delay_number"

    @property
    def native_value(self) -> float:
        until = self.coordinator.rain_delay_until
        if not until:
            return 0
        remaining = (until - dt_util.utcnow()).total_seconds()
        return max(0, round(remaining / 86400))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_rain_delay(int(value))

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
