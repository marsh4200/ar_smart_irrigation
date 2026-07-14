"""Switch entities — system master and per-program enable switches."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
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
    entities: list[SwitchEntity] = [SystemEnableSwitch(coordinator)]
    entities.extend(
        ProgramSwitch(coordinator, p.program_id, p.name) for p in coordinator.programs
    )
    async_add_entities(entities)


class SystemEnableSwitch(ARIrrigationEntity, SwitchEntity):
    """Global kill-switch. When off, no automatic programs run."""

    _attr_name = "System enabled"
    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, coordinator: ARSmartIrrigationCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_system_enabled"

    @property
    def is_on(self) -> bool:
        return self.coordinator.system_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_system_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_system_enabled(False)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class ProgramSwitch(ARIrrigationEntity, SwitchEntity):
    """Enables or disables an individual watering program."""

    _attr_icon = "mdi:calendar-clock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: ARSmartIrrigationCoordinator, program_id: str, name: str
    ) -> None:
        super().__init__(coordinator)
        self._program_id = program_id
        self._attr_name = f"Program {name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_program_{program_id}"

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_program_enabled(self._program_id)

    @property
    def extra_state_attributes(self) -> dict:
        program = self.coordinator.get_program(self._program_id)
        if not program:
            return {}
        return {
            "start_times": program.start_times,
            "frequency": program.frequency,
            "zone_count": len(program.zone_ids),
            "weather_adjust": program.weather_adjust,
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_program_enabled(self._program_id, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_program_enabled(self._program_id, False)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
