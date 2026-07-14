"""Weather-based watering adjustment and skip logic.

This module produces two things from the configured weather entity:

* a multiplicative *adjustment factor* (roughly an evapotranspiration proxy)
  used to lengthen or shorten watering based on temperature, and
* a set of *skip flags* (rain / freeze / wind) that veto a scheduled run.

It is deliberately defensive: any missing entity, attribute or forecast
service simply degrades to a neutral 1.0 factor and no skips, so a broken
weather source never stops the sprinklers from running on schedule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class WeatherDecision:
    """Outcome of evaluating the weather for a scheduled run."""

    factor: float = 1.0
    skip: bool = False
    reasons: list[str] = field(default_factory=list)
    observed_temp: float | None = None
    forecast_rain_mm: float | None = None
    wind_kmh: float | None = None


async def evaluate_weather(
    hass: HomeAssistant,
    *,
    weather_entity: str | None,
    et_enabled: bool,
    et_base_temp: float,
    rain_skip: bool,
    rain_threshold: float,
    freeze_skip: bool,
    freeze_threshold: float,
    wind_skip: bool,
    wind_threshold: float,
) -> WeatherDecision:
    """Return a WeatherDecision from the configured weather entity."""

    decision = WeatherDecision()

    if not weather_entity:
        return decision

    state = hass.states.get(weather_entity)
    if state is None or state.state in ("unknown", "unavailable"):
        _LOGGER.debug("Weather entity %s unavailable, no adjustment", weather_entity)
        return decision

    attrs = state.attributes
    temp = _as_float(attrs.get("temperature"))
    wind = _as_float(attrs.get("wind_speed"))
    decision.observed_temp = temp
    decision.wind_kmh = wind

    rain = await _forecast_precip(hass, weather_entity)
    decision.forecast_rain_mm = rain

    # --- Skips ------------------------------------------------------------
    if rain_skip and rain is not None and rain >= rain_threshold:
        decision.skip = True
        decision.reasons.append(f"rain forecast {rain:.1f}mm ≥ {rain_threshold:.1f}mm")

    if freeze_skip and temp is not None and temp <= freeze_threshold:
        decision.skip = True
        decision.reasons.append(f"temperature {temp:.1f}°C ≤ {freeze_threshold:.1f}°C")

    if wind_skip and wind is not None and wind >= wind_threshold:
        decision.skip = True
        decision.reasons.append(f"wind {wind:.0f} ≥ {wind_threshold:.0f}")

    # --- ET-ish temperature adjustment -----------------------------------
    if et_enabled and temp is not None:
        # Scale relative to the base "comfortable" temperature. Every degree
        # above base adds ~3% watering, every degree below removes it,
        # clamped to a sane 50%–150% window so a heatwave or cold snap
        # doesn't produce absurd runtimes.
        factor = 1.0 + (temp - et_base_temp) * 0.03
        decision.factor = round(max(0.5, min(1.5, factor)), 2)

    return decision


async def _forecast_precip(hass: HomeAssistant, weather_entity: str) -> float | None:
    """Sum precipitation from the next forecast day via weather.get_forecasts."""
    try:
        result = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "daily"},
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # noqa: BLE001 - forecast is best-effort
        _LOGGER.debug("Forecast lookup failed for %s: %s", weather_entity, err)
        return None

    if not result:
        return None

    forecasts = (result.get(weather_entity) or {}).get("forecast") or []
    if not forecasts:
        return None

    today = forecasts[0]
    precip = today.get("precipitation")
    if precip is None:
        prob = today.get("precipitation_probability")
        # No absolute figure — treat a high probability as a light shower.
        if prob is not None and prob >= 70:
            return 3.0
        return None
    return _as_float(precip)


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
