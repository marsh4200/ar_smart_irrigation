# AR Smart Irrigation

A hardware-agnostic smart sprinkler / irrigation controller for Home Assistant.

It doesn't talk to a specific brand of controller — instead it drives **whatever valve entities you already have** (ESPHome relays, Shelly, Sonoff, Tuya, `input_boolean`, or native `valve` entities) and layers a proper irrigation brain on top: multi-zone scheduling, sequential runs, cycle-and-soak, weather/ET adjustment, rain/freeze/wind skip, master valve + pump control, flow-based leak detection and soil-moisture skip.

Part of the **AR Smart Home** suite — [arsmarthome.co.za](https://arsmarthome.co.za).

## Features

- **Zones** map to any switch/valve/input_boolean entity, with per-zone duration, nominal flow rate, soil-moisture sensor and cycle-and-soak settings.
- **Programs** run an ordered set of zones on a schedule: multiple start times, daily / selected weekdays / even / odd / every-N-days frequency, optional per-program duration override.
- **Sequential watering** — one zone at a time, with an optional master valve / pump that opens first (configurable lead time) and closes when the run finishes.
- **Cycle-and-soak** splits a zone's runtime into pulses with soak gaps to stop runoff on clay soils and slopes.
- **Weather intelligence** using any HA `weather` entity:
  - **Rain skip** from the daily forecast precipitation.
  - **Freeze skip** below a temperature threshold.
  - **Wind skip** above a wind threshold.
  - **ET-style adjustment** that lengthens/shortens runtime with temperature.
- **Seasonal budget** — a global 0–200% multiplier, live-adjustable via a slider or service.
- **Rain delay** — suspend everything for N days.
- **Soil-moisture skip** — a zone is skipped if its moisture sensor is above threshold.
- **Flow anomaly / leak detection** — compares a flow sensor against each zone's expected flow and flags high-flow (burst), low-flow (clog) or unexpected-flow (leak) conditions.
- **Water usage** estimation per run and per day.

## Entities

| Platform | Entities |
|---|---|
| `valve` | One per zone — open to manually run, close to stop. |
| `switch` | System master enable + one enable switch per program. |
| `number` | Seasonal adjustment slider, rain-delay days. |
| `sensor` | Next run, active program, active zone, time remaining, water today, water this run, seasonal %, queued runs. |
| `binary_sensor` | Watering, rain delay active, weather skip, flow anomaly. |
| `button` | Stop all, skip current/next. |

## Services

- `ar_smart_irrigation.start_zone` (`zone_id`, optional `duration`)
- `ar_smart_irrigation.stop_zone` (`zone_id`)
- `ar_smart_irrigation.stop_all`
- `ar_smart_irrigation.run_program` (`program_id`)
- `ar_smart_irrigation.skip_next`
- `ar_smart_irrigation.rain_delay` (`days`)
- `ar_smart_irrigation.set_seasonal_adjust` (`percent`)

## Installation

**HACS (custom repository):** add `https://github.com/marsh4200/ar_smart_irrigation` as an Integration, install, restart HA.

**Manual:** copy `custom_components/ar_smart_irrigation` into your HA `config/custom_components/` folder and restart.

Then: **Settings → Devices & Services → Add Integration → AR Smart Irrigation**. Create it, then open **Configure** to add global settings, zones and programs.

## How scheduling works

The engine ticks every few seconds. On each tick it:

1. Rolls the daily water counter at midnight.
2. Checks every enabled program's start times against the clock and day pattern; matching runs are weather-evaluated and either skipped or queued.
3. Advances the active run — handling watering pulses, soak gaps, sequential zone hand-off, and master/pump control.
4. Starts the next queued run when idle.
5. Watches the flow sensor for anomalies.

Manual zone runs and `run_program` calls jump straight into the queue (a manual zone run pre-empts an active run). The global **System enabled** switch and any active **rain delay** veto all automatic runs.

## Notes

- This is a controller layer: it never talks to hardware directly, only to the entities you point it at. That's the whole design — it works with anything HA can switch.
- Water-usage figures are estimates derived from each zone's nominal flow rate (or integrated from a real flow sensor when watering). They're for budgeting, not billing.
- Single controller instance by design, which keeps services and stored state unambiguous.

## Licence

MIT.
