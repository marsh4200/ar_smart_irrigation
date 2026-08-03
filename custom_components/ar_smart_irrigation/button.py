"""Buttons: run the whole program now, or stop everything."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import IrrigationController
from .entity import IrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RunNowButton(controller), StopButton(controller)])


class RunNowButton(IrrigationEntity, ButtonEntity):
    """Run every configured zone in sequence, ignoring the weather check."""

    _attr_name = "Run now"
    _attr_icon = "mdi:play"

    def __init__(self, controller: IrrigationController) -> None:
        super().__init__(controller, "run_now")

    async def async_press(self) -> None:
        await self.controller.async_run()


class StopButton(IrrigationEntity, ButtonEntity):
    """Cancel the run and close everything."""

    _attr_name = "Stop"
    _attr_icon = "mdi:stop"

    def __init__(self, controller: IrrigationController) -> None:
        super().__init__(controller, "stop")

    async def async_press(self) -> None:
        await self.controller.async_stop()
