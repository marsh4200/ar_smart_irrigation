"""AR Smart Irrigation — a hardware-agnostic smart sprinkler controller."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_DAYS,
    ATTR_DURATION,
    ATTR_PERCENT,
    ATTR_PROGRAM_ID,
    ATTR_ZONE_ID,
    DOMAIN,
    SERVICE_RAIN_DELAY,
    SERVICE_RUN_PROGRAM,
    SERVICE_SET_SEASONAL,
    SERVICE_SKIP_NEXT,
    SERVICE_START_ZONE,
    SERVICE_STOP_ALL,
    SERVICE_STOP_ZONE,
)
from .coordinator import ARSmartIrrigationCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.VALVE,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AR Smart Irrigation from a config entry."""
    coordinator = ARSmartIrrigationCoordinator(hass, entry)
    await coordinator.async_init()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ARSmartIrrigationCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        if not hass.data[DOMAIN]:
            _unregister_services(hass)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when zones/programs/options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _first_coordinator(hass: HomeAssistant) -> ARSmartIrrigationCoordinator:
    """Return the single controller coordinator (multi-controller uses one entry)."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("AR Smart Irrigation is not set up")
    return next(iter(entries.values()))


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_STOP_ALL):
        return

    async def start_zone(call: ServiceCall) -> None:
        coord = _first_coordinator(hass)
        await coord.async_start_zone(
            call.data[ATTR_ZONE_ID], call.data.get(ATTR_DURATION)
        )

    async def stop_zone(call: ServiceCall) -> None:
        await _first_coordinator(hass).async_stop_zone(call.data[ATTR_ZONE_ID])

    async def stop_all(call: ServiceCall) -> None:
        await _first_coordinator(hass).async_stop_all()

    async def run_program(call: ServiceCall) -> None:
        await _first_coordinator(hass).async_run_program(call.data[ATTR_PROGRAM_ID])

    async def skip_next(call: ServiceCall) -> None:
        await _first_coordinator(hass).async_skip_next()

    async def rain_delay(call: ServiceCall) -> None:
        await _first_coordinator(hass).async_rain_delay(call.data[ATTR_DAYS])

    async def set_seasonal(call: ServiceCall) -> None:
        await _first_coordinator(hass).async_set_seasonal(call.data[ATTR_PERCENT])

    hass.services.async_register(
        DOMAIN, SERVICE_START_ZONE, start_zone,
        schema=vol.Schema({
            vol.Required(ATTR_ZONE_ID): cv.string,
            vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_ZONE, stop_zone,
        schema=vol.Schema({vol.Required(ATTR_ZONE_ID): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP_ALL, stop_all)
    hass.services.async_register(
        DOMAIN, SERVICE_RUN_PROGRAM, run_program,
        schema=vol.Schema({vol.Required(ATTR_PROGRAM_ID): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_SKIP_NEXT, skip_next)
    hass.services.async_register(
        DOMAIN, SERVICE_RAIN_DELAY, rain_delay,
        schema=vol.Schema({
            vol.Required(ATTR_DAYS): vol.All(vol.Coerce(int), vol.Range(min=0, max=30)),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SEASONAL, set_seasonal,
        schema=vol.Schema({
            vol.Required(ATTR_PERCENT): vol.All(vol.Coerce(int), vol.Range(min=0, max=200)),
        }),
    )


def _unregister_services(hass: HomeAssistant) -> None:
    for service in (
        SERVICE_START_ZONE,
        SERVICE_STOP_ZONE,
        SERVICE_STOP_ALL,
        SERVICE_RUN_PROGRAM,
        SERVICE_SKIP_NEXT,
        SERVICE_RAIN_DELAY,
        SERVICE_SET_SEASONAL,
    ):
        hass.services.async_remove(DOMAIN, service)
