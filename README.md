# AR Smart Irrigation

A small, weather-aware irrigation controller for Home Assistant. It drives up to
four relay channels (built for a Sonoff 4CH Pro R3) and runs them one at a time.

No flow meters, no ET maths, no soil probes. It checks the weather, then waters.

## What it does

- **Weather check before every scheduled run.** Skips if it is currently wet,
  if the outdoor temperature is below your freeze limit, or if today's forecast
  rainfall is above your threshold.
- **One daily start time**, on the days you choose.
- **Up to 4 zones**, each mapped to a relay channel with its own runtime in minutes.
- **Sequential** — only one motor ever runs at a time.
- **Manual run and stop** via buttons or services.

## Entities

| Entity | What it is |
|---|---|
| `switch.ar_smart_irrigation_program` | Master enable for the schedule. Off = no automatic runs. |
| `switch.ar_smart_irrigation_zone_1..4` | Turn on to run that zone for its set time. Turns itself off when done. |
| `sensor.ar_smart_irrigation_status` | idle / watering / skipped / disabled, with `current_zone`, `minutes_remaining`, `last_run`, `last_skip_reason`. |
| `sensor.ar_smart_irrigation_next_run` | Next scheduled start. |
| `button.ar_smart_irrigation_run_now` | Run all zones now, ignoring weather. |
| `button.ar_smart_irrigation_stop` | Cancel and switch everything off. |

## Services

```yaml
# Run everything now
service: ar_smart_irrigation.run_now

# Run only zone 2
service: ar_smart_irrigation.run_now
data:
  zone: 2

# Run all zones, but let the weather veto it
service: ar_smart_irrigation.run_now
data:
  check_weather: true

# Stop and close everything
service: ar_smart_irrigation.stop
```

## Setup

1. Copy `custom_components/ar_smart_irrigation` into your HA `config` folder,
   or add this repo to HACS as a custom repository.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → AR Smart Irrigation**.
4. Step 1: weather entity, start time, days, rain and freeze limits.
5. Step 2: pick the relay switch for each zone you use and its runtime.

Leave a zone's relay empty if you don't use that channel. Everything can be
changed later under **Configure**.

## Notes

- Leave the weather entity blank to disable weather checking entirely.
- Set the rain threshold to `0` to skip only the forecast check.
- If the weather entity is unavailable, the run goes ahead rather than being
  silently cancelled.
- The **Run now** button deliberately ignores the weather — it's a manual override.
  Use the service with `check_weather: true` if you want it respected.
