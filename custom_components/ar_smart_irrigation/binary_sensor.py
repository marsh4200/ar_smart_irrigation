"""Binary sensors for watering state and anomaly flags."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ARSmartIrrigationCoordinator
from .entity import ARIrrigationEntity


@dataclass(frozen=True, kw_only=True)
class IrrigationBinary(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool] = lambda d: False
    attrs_fn: Callable[[dict[str, Any]], dict] | None = None


BINARY_SENSORS: tuple[IrrigationBinary, ...] = (
    IrrigationBinary(
        key="watering",
        name="Watering",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:sprinkler-variant",
        value_fn=lambda d: bool(d.get("watering")),
    ),
    IrrigationBinary(
        key="rain_delay",
        name="Rain delay active",
        icon="mdi:weather-rainy",
        value_fn=lambda d: bool(d.get("rain_delayed")),
        attrs_fn=lambda d: {"until": d.get("rain_delay_until")},
    ),
    IrrigationBinary(
        key="weather_skip",
        name="Weather skip",
        icon="mdi:weather-pouring",
        value_fn=lambda d: bool(d.get("skip_reasons")),
        attrs_fn=lambda d: {"reasons": d.get("skip_reasons", [])},
    ),
    IrrigationBinary(
        key="flow_anomaly",
        name="Flow anomaly",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:pipe-leak",
        value_fn=lambda d: d.get("flow_anomaly") is not None,
        attrs_fn=lambda d: {"type": d.get("flow_anomaly")},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ARSmartIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IrrigationBinarySensor(coordinator, desc) for desc in BINARY_SENSORS
    )


class IrrigationBinarySensor(ARIrrigationEntity, BinarySensorEntity):
    entity_description: IrrigationBinary

    def __init__(
        self,
        coordinator: ARSmartIrrigationCoordinator,
        description: IrrigationBinary,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data or {}) if fn else None

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
