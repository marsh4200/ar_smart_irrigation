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
    TextSelector,
    TextSelectorConfig,
    TimeSelector,
)

from .const import (
    CONF_FREEZE_TEMP,
    CONF_PROGRAM_DAYS,
    CONF_PROGRAM_NAME,
    CONF_PROGRAM_START_TIME,
    CONF_PROGRAM_ZONES,
    CONF_RAIN_THRESHOLD,
    CONF_WEATHER_ENTITY,
    CONF_ZONE_MINUTES,
    CONF_ZONE_NAME,
    CONF_ZONE_SWITCH,
    DAYS,
    DEFAULT_FREEZE_TEMP,
    DEFAULT_MINUTES,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_START_TIME,
    DOMAIN,
    NAME,
    PROGRAM_COUNT,
    ZONE_COUNT,
)

ZONE_DOMAINS = ["switch", "valve", "input_boolean", "light"]

NO_ZONES_PLACEHOLDER = "_none"


def _weather_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_WEATHER_ENTITY,
                description={"suggested_value": defaults.get(CONF_WEATHER_ENTITY)},
            ): EntitySelector(EntitySelectorConfig(domain="weather")),
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


def _zones_schema(defaults: dict[str, Any], start: int, end: int) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for i in range(start, end + 1):
        name_key = CONF_ZONE_NAME.format(i)
        switch_key = CONF_ZONE_SWITCH.format(i)
        minutes_key = CONF_ZONE_MINUTES.format(i)
        fields[
            vol.Optional(
                name_key, description={"suggested_value": defaults.get(name_key)}
            )
        ] = TextSelector(TextSelectorConfig())
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


def _zone_options(data: dict[str, Any]) -> list[dict[str, str]]:
    """Build the zone multi-select options from whatever zones are configured so far."""
    options = []
    for i in range(1, ZONE_COUNT + 1):
        if not data.get(CONF_ZONE_SWITCH.format(i)):
            continue
        label = data.get(CONF_ZONE_NAME.format(i)) or f"Zone {i}"
        options.append({"value": str(i), "label": label})
    if not options:
        options.append({"value": NO_ZONES_PLACEHOLDER, "label": "No zones configured yet"})
    return options


def _programs_schema(defaults: dict[str, Any], zone_options: list[dict[str, str]]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for i in range(1, PROGRAM_COUNT + 1):
        name_key = CONF_PROGRAM_NAME.format(i)
        start_key = CONF_PROGRAM_START_TIME.format(i)
        days_key = CONF_PROGRAM_DAYS.format(i)
        zones_key = CONF_PROGRAM_ZONES.format(i)
        fields[
            vol.Optional(
                name_key,
                description={"suggested_value": defaults.get(name_key, f"Program {i}")},
            )
        ] = TextSelector(TextSelectorConfig())
        fields[
            vol.Required(start_key, default=defaults.get(start_key, DEFAULT_START_TIME))
        ] = TimeSelector()
        fields[
            vol.Required(days_key, default=defaults.get(days_key, DAYS))
        ] = SelectSelector(
            SelectSelectorConfig(
                options=DAYS,
                multiple=True,
                mode=SelectSelectorMode.LIST,
                translation_key="days",
            )
        )
        fields[
            vol.Optional(
                zones_key,
                description={"suggested_value": defaults.get(zones_key)},
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                options=zone_options,
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )
    return vol.Schema(fields)


def _clear_missing_zone_keys(data: dict[str, Any], user_input: dict[str, Any]) -> None:
    """Blank zone fields must actually clear rather than sticking around."""
    for i in range(1, ZONE_COUNT + 1):
        for key in (
            CONF_ZONE_NAME.format(i),
            CONF_ZONE_SWITCH.format(i),
        ):
            if key not in user_input:
                data[key] = None


def _clear_missing_program_keys(data: dict[str, Any], user_input: dict[str, Any]) -> None:
    for i in range(1, PROGRAM_COUNT + 1):
        for key in (CONF_PROGRAM_NAME.format(i), CONF_PROGRAM_ZONES.format(i)):
            if key not in user_input:
                data[key] = None


class ArSmartIrrigationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup: weather -> zones (1-16) -> programs."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zones()

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_show_form(step_id="user", data_schema=_weather_schema({}))

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_programs()

        return self.async_show_form(
            step_id="zones", data_schema=_zones_schema({}, 1, ZONE_COUNT)
        )

    async def async_step_programs(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=NAME, data=self._data)

        return self.async_show_form(
            step_id="programs",
            data_schema=_programs_schema({}, _zone_options(self._data)),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ArSmartIrrigationOptionsFlow()


class ArSmartIrrigationOptionsFlow(OptionsFlow):
    """Let everything be edited after setup: weather -> zones (1-16) -> programs."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @property
    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    @property
    def _effective(self) -> dict[str, Any]:
        """What's actually configured so far in this flow run."""
        return {**self._current, **self._data}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zones()
        return self.async_show_form(
            step_id="init", data_schema=_weather_schema(self._current)
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            _clear_missing_zone_keys(self._data, user_input)
            self._data.update(user_input)
            return await self.async_step_programs()

        return self.async_show_form(
            step_id="zones", data_schema=_zones_schema(self._current, 1, ZONE_COUNT)
        )

    async def async_step_programs(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            _clear_missing_program_keys(self._data, user_input)
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)

        return self.async_show_form(
            step_id="programs",
            data_schema=_programs_schema(self._current, _zone_options(self._effective)),
        )
