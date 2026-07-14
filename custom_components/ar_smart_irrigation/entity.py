"""Base entity for AR Smart Irrigation."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, NAME
from .coordinator import ARSmartIrrigationCoordinator


class ARIrrigationEntity(CoordinatorEntity[ARSmartIrrigationCoordinator]):
    """Common base wiring every entity to the controller device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ARSmartIrrigationCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url="https://arsmarthome.co.za",
        )
