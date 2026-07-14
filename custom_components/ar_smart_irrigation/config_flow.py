"""Config and options flow for AR Smart Irrigation."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ET_ADJUST,
    CONF_ET_BASE_TEMP,
    CONF_FLOW_HIGH_FACTOR,
    CONF_FLOW_LEAK_DETECTION,
    CONF_FLOW_LOW_FACTOR,
    CONF_FLOW_SENSOR,
    CONF_FREEZE_SKIP,
    CONF_FREEZE_THRESHOLD,
    CONF_MASTER_LEAD,
    CONF_MASTER_VALVE,
    CONF_PROGRAMS,
    CONF_PUMP_ENTITY,
    CONF_RAIN_SKIP,
    CONF_RAIN_THRESHOLD,
    CONF_WEATHER_ENTITY,
    CONF_WIND_SKIP,
    CONF_WIND_THRESHOLD,
    CONF_ZONES,
    DEFAULT_DURATION,
    DEFAULT_ET_BASE_TEMP,
    DEFAULT_FLOW_HIGH_FACTOR,
    DEFAULT_FLOW_LOW_FACTOR,
    DEFAULT_FREEZE_THRESHOLD,
    DEFAULT_MASTER_LEAD,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_SOIL_THRESHOLD,
    DEFAULT_WIND_THRESHOLD,
    DOMAIN,
    FREQ_DAILY,
    FREQUENCIES,
    NAME,
    PROGRAM_DURATION_OVERRIDE,
    PROGRAM_ENABLED,
    PROGRAM_FREQUENCY,
    PROGRAM_ID,
    PROGRAM_INTERVAL,
    PROGRAM_NAME,
    PROGRAM_START_TIMES,
    PROGRAM_WEATHER_ADJUST,
    PROGRAM_WEEKDAYS,
    PROGRAM_ZONES,
    WEEKDAYS,
    ZONE_CYCLES,
    ZONE_DURATION,
    ZONE_ENABLED,
    ZONE_FLOW_RATE,
    ZONE_ID,
    ZONE_NAME,
    ZONE_SOAK,
    ZONE_SOIL_ENTITY,
    ZONE_SOIL_THRESHOLD,
    ZONE_SWITCH,
)

_SLUG = re.compile(r"[^a-z0-9_]+")


def _slugify(text: str) -> str:
    slug = _SLUG.sub("_", text.strip().lower()).strip("_")
    return slug or "item"


class ARIrrigationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup. Detailed config lives in options."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        # Single controller instance keeps state/services unambiguous.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={CONF_ZONES: [], CONF_PROGRAMS: []},
            )
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> "ARIrrigationOptionsFlow":
        return ARIrrigationOptionsFlow(entry)


class ARIrrigationOptionsFlow(OptionsFlow):
    """Menu-driven management of settings, zones and programs."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._working: dict[str, Any] = {
            **entry.data,
            **entry.options,
        }
        self._working.setdefault(CONF_ZONES, [])
        self._working.setdefault(CONF_PROGRAMS, [])
        self._selected_zone: str | None = None
        self._selected_program: str | None = None

    # ----------------------------------------------------------------- menu
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "settings",
                "add_zone",
                "manage_zones",
                "add_program",
                "manage_programs",
            ],
        )

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title="", data=self._working)

    # ------------------------------------------------------------- settings
    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._working.update(user_input)
            return self._finish()

        w = self._working
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_WEATHER_ENTITY,
                    description={"suggested_value": w.get(CONF_WEATHER_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(
                    CONF_MASTER_VALVE,
                    description={"suggested_value": w.get(CONF_MASTER_VALVE)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch", "valve", "input_boolean"])
                ),
                vol.Optional(
                    CONF_PUMP_ENTITY,
                    description={"suggested_value": w.get(CONF_PUMP_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch", "input_boolean"])
                ),
                vol.Optional(
                    CONF_FLOW_SENSOR,
                    description={"suggested_value": w.get(CONF_FLOW_SENSOR)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_MASTER_LEAD, default=w.get(CONF_MASTER_LEAD, DEFAULT_MASTER_LEAD)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=60, unit_of_measurement="s")
                ),
                vol.Optional(
                    CONF_RAIN_SKIP, default=w.get(CONF_RAIN_SKIP, True)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_RAIN_THRESHOLD,
                    default=w.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=50, step=0.5, unit_of_measurement="mm")
                ),
                vol.Optional(
                    CONF_FREEZE_SKIP, default=w.get(CONF_FREEZE_SKIP, True)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_FREEZE_THRESHOLD,
                    default=w.get(CONF_FREEZE_THRESHOLD, DEFAULT_FREEZE_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10, max=15, step=0.5, unit_of_measurement="°C")
                ),
                vol.Optional(
                    CONF_WIND_SKIP, default=w.get(CONF_WIND_SKIP, False)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_WIND_THRESHOLD,
                    default=w.get(CONF_WIND_THRESHOLD, DEFAULT_WIND_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=120, unit_of_measurement="km/h")
                ),
                vol.Optional(
                    CONF_ET_ADJUST, default=w.get(CONF_ET_ADJUST, True)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_ET_BASE_TEMP,
                    default=w.get(CONF_ET_BASE_TEMP, DEFAULT_ET_BASE_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=35, step=0.5, unit_of_measurement="°C")
                ),
                vol.Optional(
                    CONF_FLOW_LEAK_DETECTION,
                    default=w.get(CONF_FLOW_LEAK_DETECTION, False),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_FLOW_HIGH_FACTOR,
                    default=w.get(CONF_FLOW_HIGH_FACTOR, DEFAULT_FLOW_HIGH_FACTOR),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1.1, max=5, step=0.1)
                ),
                vol.Optional(
                    CONF_FLOW_LOW_FACTOR,
                    default=w.get(CONF_FLOW_LOW_FACTOR, DEFAULT_FLOW_LOW_FACTOR),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=0.9, step=0.05)
                ),
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    # ---------------------------------------------------------------- zones
    def _zone_schema(self, zone: dict[str, Any] | None = None) -> vol.Schema:
        z = zone or {}
        return vol.Schema(
            {
                vol.Required(ZONE_NAME, default=z.get(ZONE_NAME, "")): selector.TextSelector(),
                vol.Required(
                    ZONE_SWITCH,
                    description={"suggested_value": z.get(ZONE_SWITCH)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["switch", "valve", "input_boolean"]
                    )
                ),
                vol.Required(
                    ZONE_DURATION, default=z.get(ZONE_DURATION, DEFAULT_DURATION)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=180, unit_of_measurement="min")
                ),
                vol.Optional(
                    ZONE_FLOW_RATE,
                    description={"suggested_value": z.get(ZONE_FLOW_RATE)},
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=200, step=0.5, unit_of_measurement="L/min")
                ),
                vol.Optional(
                    ZONE_CYCLES, default=z.get(ZONE_CYCLES, 1)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=6)
                ),
                vol.Optional(
                    ZONE_SOAK, default=z.get(ZONE_SOAK, 0)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=60, unit_of_measurement="min")
                ),
                vol.Optional(
                    ZONE_SOIL_ENTITY,
                    description={"suggested_value": z.get(ZONE_SOIL_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    ZONE_SOIL_THRESHOLD,
                    default=z.get(ZONE_SOIL_THRESHOLD, DEFAULT_SOIL_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, unit_of_measurement="%")
                ),
                vol.Optional(
                    ZONE_ENABLED, default=z.get(ZONE_ENABLED, True)
                ): selector.BooleanSelector(),
            }
        )

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            zones = list(self._working[CONF_ZONES])
            zone_id = self._unique_zone_id(user_input[ZONE_NAME])
            user_input[ZONE_ID] = zone_id
            zones.append(user_input)
            self._working[CONF_ZONES] = zones
            return self._finish()
        return self.async_show_form(step_id="add_zone", data_schema=self._zone_schema())

    async def async_step_manage_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        zones = self._working[CONF_ZONES]
        if not zones:
            return self.async_abort(reason="no_zones")
        if user_input is not None:
            self._selected_zone = user_input["zone"]
            return await self.async_step_zone_menu()
        options = [
            selector.SelectOptionDict(value=z[ZONE_ID], label=z[ZONE_NAME])
            for z in zones
        ]
        schema = vol.Schema(
            {
                vol.Required("zone"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options)
                )
            }
        )
        return self.async_show_form(step_id="manage_zones", data_schema=schema)

    async def async_step_zone_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="zone_menu", menu_options=["edit_zone", "delete_zone"]
        )

    async def async_step_edit_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        zone = self._get_zone(self._selected_zone)
        if user_input is not None:
            user_input[ZONE_ID] = zone[ZONE_ID]
            self._working[CONF_ZONES] = [
                user_input if z[ZONE_ID] == zone[ZONE_ID] else z
                for z in self._working[CONF_ZONES]
            ]
            return self._finish()
        return self.async_show_form(
            step_id="edit_zone", data_schema=self._zone_schema(zone)
        )

    async def async_step_delete_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        zid = self._selected_zone
        self._working[CONF_ZONES] = [
            z for z in self._working[CONF_ZONES] if z[ZONE_ID] != zid
        ]
        # Scrub the deleted zone from any programs that referenced it.
        for program in self._working[CONF_PROGRAMS]:
            program[PROGRAM_ZONES] = [z for z in program.get(PROGRAM_ZONES, []) if z != zid]
        return self._finish()

    # ------------------------------------------------------------- programs
    def _program_schema(self, program: dict[str, Any] | None = None) -> vol.Schema:
        p = program or {}
        zone_options = [
            selector.SelectOptionDict(value=z[ZONE_ID], label=z[ZONE_NAME])
            for z in self._working[CONF_ZONES]
        ]
        weekday_options = [
            selector.SelectOptionDict(value=str(i), label=day.capitalize())
            for i, day in enumerate(WEEKDAYS)
        ]
        return vol.Schema(
            {
                vol.Required(PROGRAM_NAME, default=p.get(PROGRAM_NAME, "")): selector.TextSelector(),
                vol.Required(
                    PROGRAM_ZONES, default=p.get(PROGRAM_ZONES, [])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=zone_options, multiple=True)
                ),
                vol.Required(
                    PROGRAM_START_TIMES,
                    default=",".join(p.get(PROGRAM_START_TIMES, [])) or "06:00",
                ): selector.TextSelector(),
                vol.Required(
                    PROGRAM_FREQUENCY, default=p.get(PROGRAM_FREQUENCY, FREQ_DAILY)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=FREQUENCIES, translation_key="frequency"
                    )
                ),
                vol.Optional(
                    PROGRAM_WEEKDAYS,
                    default=[str(d) for d in p.get(PROGRAM_WEEKDAYS, [])],
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=weekday_options, multiple=True)
                ),
                vol.Optional(
                    PROGRAM_INTERVAL, default=p.get(PROGRAM_INTERVAL, 2)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=30, unit_of_measurement="days")
                ),
                vol.Optional(
                    PROGRAM_DURATION_OVERRIDE,
                    description={"suggested_value": p.get(PROGRAM_DURATION_OVERRIDE)},
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=180, unit_of_measurement="min")
                ),
                vol.Optional(
                    PROGRAM_WEATHER_ADJUST, default=p.get(PROGRAM_WEATHER_ADJUST, True)
                ): selector.BooleanSelector(),
                vol.Optional(
                    PROGRAM_ENABLED, default=p.get(PROGRAM_ENABLED, True)
                ): selector.BooleanSelector(),
            }
        )

    def _normalise_program(self, data: dict[str, Any]) -> dict[str, Any]:
        times = [
            t.strip()
            for t in str(data.get(PROGRAM_START_TIMES, "")).split(",")
            if _valid_time(t.strip())
        ]
        data[PROGRAM_START_TIMES] = times or ["06:00"]
        data[PROGRAM_WEEKDAYS] = [int(d) for d in data.get(PROGRAM_WEEKDAYS, [])]
        return data

    async def async_step_add_program(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._working[CONF_ZONES]:
            return self.async_abort(reason="no_zones")
        if user_input is not None:
            user_input = self._normalise_program(user_input)
            user_input[PROGRAM_ID] = self._unique_program_id(user_input[PROGRAM_NAME])
            self._working[CONF_PROGRAMS] = [
                *self._working[CONF_PROGRAMS],
                user_input,
            ]
            return self._finish()
        return self.async_show_form(
            step_id="add_program", data_schema=self._program_schema()
        )

    async def async_step_manage_programs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        programs = self._working[CONF_PROGRAMS]
        if not programs:
            return self.async_abort(reason="no_programs")
        if user_input is not None:
            self._selected_program = user_input["program"]
            return await self.async_step_program_menu()
        options = [
            selector.SelectOptionDict(value=p[PROGRAM_ID], label=p[PROGRAM_NAME])
            for p in programs
        ]
        schema = vol.Schema(
            {
                vol.Required("program"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options)
                )
            }
        )
        return self.async_show_form(step_id="manage_programs", data_schema=schema)

    async def async_step_program_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="program_menu", menu_options=["edit_program", "delete_program"]
        )

    async def async_step_edit_program(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        program = self._get_program(self._selected_program)
        if user_input is not None:
            user_input = self._normalise_program(user_input)
            user_input[PROGRAM_ID] = program[PROGRAM_ID]
            self._working[CONF_PROGRAMS] = [
                user_input if p[PROGRAM_ID] == program[PROGRAM_ID] else p
                for p in self._working[CONF_PROGRAMS]
            ]
            return self._finish()
        return self.async_show_form(
            step_id="edit_program", data_schema=self._program_schema(program)
        )

    async def async_step_delete_program(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        pid = self._selected_program
        self._working[CONF_PROGRAMS] = [
            p for p in self._working[CONF_PROGRAMS] if p[PROGRAM_ID] != pid
        ]
        return self._finish()

    # ------------------------------------------------------------- helpers
    def _get_zone(self, zone_id: str | None) -> dict[str, Any]:
        return next(z for z in self._working[CONF_ZONES] if z[ZONE_ID] == zone_id)

    def _get_program(self, program_id: str | None) -> dict[str, Any]:
        return next(p for p in self._working[CONF_PROGRAMS] if p[PROGRAM_ID] == program_id)

    def _unique_zone_id(self, name: str) -> str:
        return _unique_id(_slugify(name), {z[ZONE_ID] for z in self._working[CONF_ZONES]})

    def _unique_program_id(self, name: str) -> str:
        return _unique_id(
            _slugify(name), {p[PROGRAM_ID] for p in self._working[CONF_PROGRAMS]}
        )


def _unique_id(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def _valid_time(value: str) -> bool:
    return bool(re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", value))
