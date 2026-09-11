"""Constants for AR Smart Irrigation."""

from __future__ import annotations

DOMAIN = "ar_smart_irrigation"
NAME = "AR Smart Irrigation"
MANUFACTURER = "AR Smart Home"
MODEL = "Smart Irrigation Controller"
VERSION = "2.0.0"

ZONE_COUNT = 4
PROGRAM_COUNT = 4

# ---------------------------------------------------------------------------
# Global (weather) config keys
# ---------------------------------------------------------------------------
CONF_WEATHER_ENTITY = "weather_entity"
CONF_RAIN_THRESHOLD = "rain_threshold"
CONF_FREEZE_TEMP = "freeze_temp"

# ---------------------------------------------------------------------------
# Zone config keys — one physical switch/valve entity per zone
# ---------------------------------------------------------------------------
CONF_ZONE_SWITCH = "zone_{}_switch"
CONF_ZONE_NAME = "zone_{}_name"
CONF_ZONE_MINUTES = "zone_{}_minutes"

# ---------------------------------------------------------------------------
# Program config keys — a program is a named timer: a start time, the days it
# runs on, and which zones it triggers.
# ---------------------------------------------------------------------------
CONF_PROGRAM_NAME = "program_{}_name"
CONF_PROGRAM_START_TIME = "program_{}_start_time"
CONF_PROGRAM_DAYS = "program_{}_days"
CONF_PROGRAM_ZONES = "program_{}_zones"

# Legacy (v1) config keys, kept only so old entries can be migrated.
CONF_START_TIME = "start_time"
CONF_DAYS = "days"

DEFAULT_START_TIME = "06:00:00"
DEFAULT_RAIN_THRESHOLD = 2.0  # mm forecast for today
DEFAULT_FREEZE_TEMP = 4.0  # degrees
DEFAULT_MINUTES = 10

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Weather conditions we treat as "it's wet out there, skip it"
WET_CONDITIONS = {
    "rainy",
    "pouring",
    "lightning",
    "lightning-rainy",
    "hail",
    "snowy",
    "snowy-rainy",
}

# Controller status values
STATUS_IDLE = "idle"
STATUS_WATERING = "watering"
STATUS_SKIPPED = "skipped"
STATUS_DISABLED = "disabled"

SERVICE_RUN_NOW = "run_now"
SERVICE_STOP = "stop"
SERVICE_RUN_PROGRAM = "run_program"

PLATFORMS = ["switch", "sensor", "binary_sensor", "button"]
