import httpx
import asyncio
import logging
import math
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Variables requested from Open-Meteo on every call.
#
# soil_moisture_* is requested because the problem statement names soil moisture
# explicitly and Open-Meteo serves it free and keyless. It is NOT a model input
# yet - the trained Random Forest consumes SoilGrids soil *texture* (clay / sand
# / silt), which is a static property of the ground, not today's wetness. Live
# moisture is reported to the UI as a trigger condition and labelled as such.
#
# past_days=7 is what makes real antecedent rainfall possible: 24h / 3-day /
# 7-day totals are summed from measured history rather than extrapolated from a
# 24-hour series the way the earlier version did.
HOURLY_VARS = ("precipitation,precipitation_probability,windspeed_10m,"
               "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,temperature_2m")
PAST_DAYS = 7
FORECAST_DAYS = 2


async def _fetch_cell_forecast(client: httpx.AsyncClient, cell: Dict[str, Any]) -> tuple:
    """Fetch measured + forecast hourly weather for one cell centroid."""
    cell_id = cell.get("location_id")
    lat = cell.get("centroid_lat", 0.0)
    lon = cell.get("centroid_lon", 0.0)

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": HOURLY_VARS,
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": "Asia/Kolkata",
    }

    try:
        response = await client.get(OPEN_METEO_URL, params=params, timeout=20.0)
        response.raise_for_status()
        data = response.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        precip = hourly.get("precipitation", [])
        prob = hourly.get("precipitation_probability", [])
        wind = hourly.get("windspeed_10m", [])
        sm07 = hourly.get("soil_moisture_0_to_7cm", [])
        sm728 = hourly.get("soil_moisture_7_to_28cm", [])
        temp = hourly.get("temperature_2m", [])

        if not times:
            raise ValueError("Open-Meteo returned no hourly series")

        series = []
        for i, t in enumerate(times):
            series.append({
                "time": t,
                "precipitation": float(precip[i] if i < len(precip) and precip[i] is not None else 0.0),
                "precip_probability": float(prob[i] if i < len(prob) and prob[i] is not None else 0.0),
                "wind_speed": float(wind[i] if i < len(wind) and wind[i] is not None else 0.0),
                "soil_moisture_0_to_7cm": (float(sm07[i]) if i < len(sm07) and sm07[i] is not None else None),
                "soil_moisture_7_to_28cm": (float(sm728[i]) if i < len(sm728) and sm728[i] is not None else None),
                "temperature_2m": (float(temp[i]) if i < len(temp) and temp[i] is not None else None),
                "synthetic": False,
            })

        return cell_id, series

    except Exception as e:
        logger.warning(f"[WeatherService] Live fetch failed for {cell_id} "
                       f"(lat={lat}, lon={lon}): {e}")
        return cell_id, _synthetic_fallback(cell)


def _synthetic_fallback(cell: Dict[str, Any]) -> List[Dict]:
    """Clearly-labelled synthetic series, used ONLY when the live API fails.

    Every entry is tagged synthetic=True so no caller can present it as an
    observation. The Risk Map treats a synthetic series as "no live data" rather
    than as rainfall, because a fabricated number that reaches a rainfall
    threshold could raise a false warning.
    """
    import random

    rng = random.Random(str(cell.get("location_id", "x")))
    base_precip = (cell.get("base_susceptibility", 0.5) or 0.5) * 25
    historical_boost = min(cell.get("historical_count", 0) or 0, 5) * 3

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    series = []
    for i in range(PAST_DAYS * 24 + FORECAST_DAYS * 24):
        hour = (now + timedelta(hours=i - PAST_DAYS * 24)).hour
        time_factor = 1.0 + (0.8 if 10 <= hour <= 18 else 0.0)
        noise = rng.uniform(0.6, 1.4)
        precip = round(base_precip * time_factor * noise + historical_boost * (i / 24), 2)
        series.append({
            "time": (now + timedelta(hours=i - PAST_DAYS * 24)).isoformat(),
            "precipitation": precip,
            "precip_probability": min(int(precip * 3), 100),
            "wind_speed": round(rng.uniform(5, 20), 1),
            "soil_moisture_0_to_7cm": None,
            "soil_moisture_7_to_28cm": None,
            "temperature_2m": None,
            "synthetic": True,
        })
    return series


def _is_synthetic(series: List[Dict]) -> bool:
    return bool(series) and all(e.get("synthetic") for e in series)


async def fetch_24h_forecast(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fetch hourly weather history + forecast from Open-Meteo for each cell.

    Returns the same {"source", "resolution", "data"} contract the forecast
    engine already consumes, with one addition: "live" is False for any cell
    whose series is synthetic, so downstream code can refuse to treat a
    fabricated series as a measurement.
    """
    if not cells:
        return {"source": "Open-Meteo", "resolution": "9km", "data": {}, "live": {}}

    result = {}
    live = {}
    async with httpx.AsyncClient() as client:
        tasks = [_fetch_cell_forecast(client, cell) for cell in cells]
        responses = await asyncio.gather(*tasks)
        for cell_id, series in responses:
            result[cell_id] = series
            live[cell_id] = not _is_synthetic(series)

    any_live = any(live.values())
    return {
        "source": "Open-Meteo ERA5 + ICON (live)" if any_live else "Open-Meteo unavailable",
        "resolution": "9km",
        "data": result,
        "live": live,
    }