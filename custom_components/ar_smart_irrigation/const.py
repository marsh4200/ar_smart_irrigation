"""Constants for the AR Smart Irrigation integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "ar_smart_irrigation"
NAME = "AR Smart Irrigation"
MANUFACTURER = "AR Smart Home"
MODEL = "Smart Irrigation Controller"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.state"

# How often the watering engine ticks. Irrigation doesn't need sub-second
# resolution, but a short tick keeps zone transitions and the UI responsive.
ENGINE_TICK = timedelta(seconds=5)

# --- Config entry / options keys -------------------------------------------
CONF_ZONES = "zones"
CONF_PROGRAMS = "programs"

CONF_WEATHER_ENTITY = "weather_entity"
CONF_MASTER_VALVE = "master_valve_entity"
CONF_PUMP_ENTITY = "pump_entity"
CONF_FLOW_SENSOR = "flow_sensor_entity"

CONF_MASTER_LEAD = "master_lead_seconds"

CONF_RAIN_SKIP = "rain_skip_enabled"
CONF_RAIN_THRESHOLD = "rain_threshold_mm"
CONF_FREEZE_SKIP = "freeze_skip_enabled"
CONF_FREEZE_THRESHOLD = "freeze_threshold_c"
CONF_WIND_SKIP = "wind_skip_enabled"
CONF_WIND_THRESHOLD = "wind_threshold_kmh"

CONF_ET_ADJUST = "et_adjust_enabled"
CONF_ET_BASE_TEMP = "et_base_temp_c"

CONF_SEASONAL_ADJUST = "seasonal_adjust"

CONF_FLOW_LEAK_DETECTION = "flow_leak_detection"
CONF_FLOW_HIGH_FACTOR = "flow_high_factor"
CONF_FLOW_LOW_FACTOR = "flow_low_factor"

# --- Zone keys --------------------------------------------------------------
ZONE_ID = "zone_id"
ZONE_NAME = "name"
ZONE_SWITCH = "switch_entity"
ZONE_DURATION = "default_duration"        # minutes
ZONE_FLOW_RATE = "flow_rate"              # litres / minute (nominal)
ZONE_AREA = "area"                        # m2 (optional, informational)
ZONE_SOIL_ENTITY = "soil_moisture_entity"
ZONE_SOIL_THRESHOLD = "soil_moisture_threshold"  # % above which we skip
ZONE_CYCLES = "cycles"                    # cycle-and-soak: number of pulses
ZONE_SOAK = "soak_minutes"                # soak time between pulses
ZONE_ENABLED = "enabled"

# --- Program keys -----------------------------------------------------------
PROGRAM_ID = "program_id"
PROGRAM_NAME = "name"
PROGRAM_ZONES = "zone_ids"
PROGRAM_START_TIMES = "start_times"
PROGRAM_FREQUENCY = "frequency"           # see FREQ_* below
PROGRAM_WEEKDAYS = "weekdays"             # list[int] 0=Mon .. 6=Sun
PROGRAM_INTERVAL = "interval_days"
PROGRAM_DURATION_OVERRIDE = "duration_override"  # minutes, optional
PROGRAM_WEATHER_ADJUST = "weather_adjust"
PROGRAM_ENABLED = "enabled"

FREQ_DAILY = "daily"
FREQ_WEEKDAYS = "weekdays"
FREQ_EVEN = "even"
FREQ_ODD = "odd"
FREQ_INTERVAL = "interval"
FREQUENCIES = [FREQ_DAILY, FREQ_WEEKDAYS, FREQ_EVEN, FREQ_ODD, FREQ_INTERVAL]

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# --- Defaults ---------------------------------------------------------------
DEFAULT_DURATION = 10
DEFAULT_CYCLES = 1
DEFAULT_SOAK = 0
DEFAULT_SOIL_THRESHOLD = 60
DEFAULT_RAIN_THRESHOLD = 3.0
DEFAULT_FREEZE_THRESHOLD = 2.0
DEFAULT_WIND_THRESHOLD = 40.0
DEFAULT_ET_BASE_TEMP = 20.0
DEFAULT_MASTER_LEAD = 3
DEFAULT_SEASONAL = 100
DEFAULT_FLOW_HIGH_FACTOR = 1.5
DEFAULT_FLOW_LOW_FACTOR = 0.3
FLOW_ANOMALY_TICKS = 6  # sustained ticks (~30s) before flagging

# --- Run phases -------------------------------------------------------------
PHASE_WATERING = "watering"
PHASE_SOAKING = "soaking"

# --- Services ---------------------------------------------------------------
SERVICE_START_ZONE = "start_zone"
SERVICE_STOP_ZONE = "stop_zone"
SERVICE_STOP_ALL = "stop_all"
SERVICE_RUN_PROGRAM = "run_program"
SERVICE_SKIP_NEXT = "skip_next"
SERVICE_RAIN_DELAY = "rain_delay"
SERVICE_SET_SEASONAL = "set_seasonal_adjust"

ATTR_ZONE_ID = "zone_id"
ATTR_PROGRAM_ID = "program_id"
ATTR_DURATION = "duration"
ATTR_DAYS = "days"
ATTR_PERCENT = "percent"

# Signals
SIGNAL_UPDATE = f"{DOMAIN}_update"
