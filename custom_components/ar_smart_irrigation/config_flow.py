"""Config flow for AR Smart Irrigation."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TimeSelector,
)

from .const import (
    CONF_DAYS,
    CONF_FREEZE_TEMP,
    CONF_RAIN_THRESHOLD,
    CONF_START_TIME,
    CONF_WEATHER_ENTITY,
    CONF_ZONE_MINUTES,
    CONF_ZONE_SWITCH,
    DAYS,
    DEFAULT_FREEZE_TEMP,
    DEFAULT_MINUTES,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_START_TIME,
    DOMAIN,
    NAME,
    ZONE_COUNT,
)

ZONE_DOMAINS = ["switch", "valve", "input_boolean", "light"]


def _program_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_WEATHER_ENTITY,
                description={"suggested_value": defaults.get(CONF_WEATHER_ENTITY)},
            ): EntitySelector(EntitySelectorConfig(domain="weather")),
            vol.Required(
                CONF_START_TIME,
                default=defaults.get(CONF_START_TIME, DEFAULT_START_TIME),
            ): TimeSelector(),
            vol.Required(
                CONF_DAYS, default=defaults.get(CONF_DAYS, DAYS)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=DAYS,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                    translation_key="days",
                )
            ),
            vol.Required(
                CONF_RAIN_THRESHOLD,
                default=defaults.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=25, step=0.5, unit_of_measurement="mm",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_FREEZE_TEMP,
                default=defaults.get(CONF_FREEZE_TEMP, DEFAULT_FREEZE_TEMP),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=-10, max=15, step=1, unit_of_measurement="°",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _zones_schema(defaults: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for i in range(1, ZONE_COUNT + 1):
        switch_key = CONF_ZONE_SWITCH.format(i)
        minutes_key = CONF_ZONE_MINUTES.format(i)
        fields[
            vol.Optional(
                switch_key, description={"suggested_value": defaults.get(switch_key)}
            )
        ] = EntitySelector(EntitySelectorConfig(domain=ZONE_DOMAINS))
        fields[
            vol.Optional(minutes_key, default=defaults.get(minutes_key, DEFAULT_MINUTES))
        ] = NumberSelector(
            NumberSelectorConfig(
                min=1, max=180, step=1, unit_of_measurement="min",
                mode=NumberSelectorMode.BOX,
            )
        )
    return vol.Schema(fields)


class ArSmartIrrigationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zones()

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_show_form(step_id="user", data_schema=_program_schema({}))

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=NAME, data=self._data)

        return self.async_show_form(step_id="zones", data_schema=_zones_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ArSmartIrrigationOptionsFlow()


class ArSmartIrrigationOptionsFlow(OptionsFlow):
    """Let everything be edited after setup."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @property
    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zones()
        return self.async_show_form(
            step_id="init", data_schema=_program_schema(self._current)
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            # Blank zone entities must actually clear.
            for i in range(1, ZONE_COUNT + 1):
                key = CONF_ZONE_SWITCH.format(i)
                if key not in user_input:
                    self._data[key] = None
            return self.async_create_entry(title="", data=self._data)

        return self.async_show_form(
            step_id="zones", data_schema=_zones_schema(self._current)
        )
