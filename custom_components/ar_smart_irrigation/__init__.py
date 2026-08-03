"""AR Smart Irrigation - a small, weather-aware relay irrigation controller."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_RUN_NOW,
    SERVICE_STOP,
    ZONE_COUNT,
)
from .controller import IrrigationController

_LOGGER = logging.getLogger(__name__)

RUN_NOW_SCHEMA = vol.Schema(
    {
        vol.Optional("zone"): vol.All(vol.Coerce(int), vol.Range(min=1, max=ZONE_COUNT)),
        vol.Optional("check_weather", default=False): cv.boolean,
    }
)

STOP_SCHEMA = vol.Schema({})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    controller = IrrigationController(hass, entry)
    await controller.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        controller: IrrigationController = hass.data[DOMAIN].pop(entry.entry_id)
        await controller.async_unload()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_RUN_NOW)
            hass.services.async_remove(DOMAIN, SERVICE_STOP)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register the two services once."""
    if hass.services.has_service(DOMAIN, SERVICE_RUN_NOW):
        return

    def _controllers() -> list[IrrigationController]:
        return list(hass.data.get(DOMAIN, {}).values())

    async def _run_now(call: ServiceCall) -> None:
        zone = call.data.get("zone")
        zones = [zone] if zone else None
        for controller in _controllers():
            await controller.async_run(zones, check_weather=call.data.get("check_weather", False))

    async def _stop(_call: ServiceCall) -> None:
        for controller in _controllers():
            await controller.async_stop()

    hass.services.async_register(DOMAIN, SERVICE_RUN_NOW, _run_now, schema=RUN_NOW_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_STOP, _stop, schema=STOP_SCHEMA)
