"""Constants for AR Smart Irrigation (simple)."""

from __future__ import annotations

DOMAIN = "ar_smart_irrigation"
NAME = "AR Smart Irrigation"
MANUFACTURER = "AR Smart Home"
MODEL = "Simple Irrigation Controller"
VERSION = "1.0.0"

ZONE_COUNT = 4

# Config keys
CONF_WEATHER_ENTITY = "weather_entity"
CONF_START_TIME = "start_time"
CONF_DAYS = "days"
CONF_RAIN_THRESHOLD = "rain_threshold"
CONF_FREEZE_TEMP = "freeze_temp"

CONF_ZONE_SWITCH = "zone_{}_switch"
CONF_ZONE_MINUTES = "zone_{}_minutes"

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

PLATFORMS = ["switch", "sensor", "button"]
