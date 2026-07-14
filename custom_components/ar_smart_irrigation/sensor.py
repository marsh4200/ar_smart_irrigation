"""Sensor entities exposing irrigation status and telemetry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ARSmartIrrigationCoordinator
from .entity import ARIrrigationEntity


@dataclass(frozen=True, kw_only=True)
class IrrigationSensor(SensorEntityDescription):
    """Sensor description with a value extractor over coordinator.data."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda d: None


SENSORS: tuple[IrrigationSensor, ...] = (
    IrrigationSensor(
        key="next_run",
        name="Next scheduled run",
        icon="mdi:calendar-arrow-right",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.get("next_run"),
    ),
    IrrigationSensor(
        key="active_program",
        name="Active program",
        icon="mdi:play-circle",
        value_fn=lambda d: d.get("active_program") or "Idle",
    ),
    IrrigationSensor(
        key="active_zone",
        name="Active zone",
        icon="mdi:sprinkler",
        value_fn=lambda d: d.get("active_zone") or "None",
    ),
    IrrigationSensor(
        key="remaining_seconds",
        name="Zone time remaining",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("remaining_seconds", 0),
    ),
    IrrigationSensor(
        key="water_used_today",
        name="Water used today",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("water_used_today", 0.0),
    ),
    IrrigationSensor(
        key="run_litres",
        name="Water this run",
        icon="mdi:water-pump",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("run_litres", 0.0),
    ),
    IrrigationSensor(
        key="seasonal_adjust",
        name="Seasonal adjustment",
        icon="mdi:percent",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("seasonal_adjust", 100),
    ),
    IrrigationSensor(
        key="queue_depth",
        name="Queued runs",
        icon="mdi:tray-full",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("queue_depth", 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ARSmartIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IrrigationStatusSensor(coordinator, desc) for desc in SENSORS
    )


class IrrigationStatusSensor(ARIrrigationEntity, SensorEntity):
    """Generic sensor rendered from a coordinator.data extractor."""

    entity_description: IrrigationSensor

    def __init__(
        self,
        coordinator: ARSmartIrrigationCoordinator,
        description: IrrigationSensor,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return self.entity_description.value_fn(data)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
