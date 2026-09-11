# AR Smart Irrigation

A small, weather-aware irrigation controller for Home Assistant. It drives up to
sixteen relay channels (any `switch`, `valve`, `input_boolean`, or `light`
entity works — built with a Sonoff 4CH Pro R3 in mind, but scales to a large
multi-zone property) and runs them one at a time.

No flow meters, no ET maths, no soil probes. It checks the weather, then waters —
on as many independent timers as you need.

## What it does

- **Multiple programs (timers).** Set up to 4 independent programs, each with
  its own name, start time, days of the week, and choice of zones. Run a
  "Morning" program on some zones and an "Evening" program on others, or run
  them all from one program — your call.
- **Weather check before every scheduled run.** Skips if it is currently wet,
  if the outdoor temperature is below your freeze limit, or if today's forecast
  rainfall is above your threshold. Applies to every program.
- **Up to 16 zones**, each mapped to a switch entity, with its own name and
  runtime in minutes. Leave a zone's switch entity empty and it's simply not
  created — nothing to disable, it just doesn't exist until you pick an
  entity for it (in **Configure**, at any time).
- **Sequential** — only one zone ever runs at a time, even across programs.
- **Skip today** — a one-tap switch that cancels only today's scheduled
  run(s), without touching your program or day-of-week setup. Clears itself
  automatically at midnight.
- **Per-program enable switches** — turn an individual program on or off
  without affecting the others.
- **A single System switch** — the master kill switch for the whole
  integration. Off means nothing runs, ever, on any program.
- **Manual run and stop** via switches, buttons, or services.

## Entities

| Entity | What it is |
|---|---|
| `switch.ar_smart_irrigation_system` | Master enable for the whole integration. Off = no automatic or manual runs. |
| `switch.ar_smart_irrigation_skip_today` | Skip every scheduled run today only. Auto-clears at midnight. |
| `switch.ar_smart_irrigation_<program>_enabled` | Enable/disable one program, one per configured program. |
| `switch.ar_smart_irrigation_<zone name>` | Turn on to run that zone for its set time. Turns itself off when done. |
| `binary_sensor.ar_smart_irrigation_watering` | On while any zone is actively running. |
| `binary_sensor.ar_smart_irrigation_last_run_skipped` | On if the last scheduled run was skipped, with the reason as an attribute. |
| `sensor.ar_smart_irrigation_status` | idle / watering / skipped / disabled, with `current_zone`, `current_program`, `minutes_remaining`, `last_run`, `last_skip_reason`. |
| `sensor.ar_smart_irrigation_next_run` | Next scheduled start, across every enabled program. |
| `button.ar_smart_irrigation_run_now` | Run every configured zone now, ignoring the weather. |
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

# Run a specific program by number
service: ar_smart_irrigation.run_program
data:
  program: 1
  check_weather: true

# Stop and close everything
service: ar_smart_irrigation.stop
```

## Setup

1. Copy `custom_components/ar_smart_irrigation` into your HA `config` folder,
   or add this repo to HACS as a custom repository.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → AR Smart Irrigation**.
4. Step 1: weather entity, rain and freeze limits (these protect every
   program you configure next).
5. Steps 2 & 3: name each zone and pick its switch entity and runtime, for
   zones 1-8 then 9-16. Leave a zone empty if you don't use that channel.
6. Step 4: build your programs — name, start time, days, and which zones each
   one triggers. Leave a program's zones empty to leave it unused.

Everything can be changed later under **Configure**.

## Notes

- Leave the weather entity blank to disable weather checking entirely.
- Set the rain threshold to `0` to skip only the forecast check.
- If the weather entity is unavailable, the run goes ahead rather than being
  silently cancelled.
- The **Run now** button and the per-zone switches deliberately ignore the
  weather — they're manual overrides. Use `run_now`/`run_program` with
  `check_weather: true` if you want them respected.
- Upgrading from v1 (single start time/days)? Your old schedule is migrated
  automatically into "Program 1" the first time you restart on v2 — nothing
  to redo.
