"""
Live environmental conditions per monitoring cell.

What this is
  The measurement half of the early-warning loop. Every cycle it pulls hourly
  rainfall and soil moisture for each cell centroid from Open-Meteo, then sums
  real measured history into the antecedent windows that landslide triggering
  actually depends on:

      rainfall_1h   rainfall_24h   rainfall_3d   rainfall_7d
      soil_moisture_0_to_7cm   soil_moisture_7_to_28cm   temperature_2m

Why antecedent windows are summed, not extrapolated
  The previous implementation held only a 24-hour series and approximated the
  3-day total as `24h * 2.5` and the 7-day as `24h * 5.0`. Those constants are
  invented: a dry week with one wet day produced a large 7-day total. Open-Meteo
  serves 7 days of hourly history, so these are now real sums of measured values.

Honesty rule
  A failed fetch returns available=False and a reason. It never returns a
  fabricated series, because a synthetic rainfall number crossing a threshold
  would raise a real warning for a place where nothing was measured.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

WINDOWS = {"rainfall_24h_mm": 24, "rainfall_3d_mm": 72, "rainfall_7d_mm": 168}


def _now_index(series: List[Dict[str, Any]]) -> int:
    """Index of the most recent hour that is not in the future."""
    now = datetime.now(IST).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    idx = 0
    for i, entry in enumerate(series):
        try:
            t = datetime.fromisoformat(str(entry["time"]))
        except (ValueError, KeyError):
            continue
        if t.tzinfo is not None:
            t = t.astimezone(IST).replace(tzinfo=None)
        if t <= now:
            idx = i
        else:
            break
    return idx


def _sum_window(series: List[Dict], end_idx: int, hours: int) -> float:
    start = max(0, end_idx - hours + 1)
    total = 0.0
    for entry in series[start:end_idx + 1]:
        total += float(entry.get("precipitation") or 0.0)
    return round(total, 2)


def _latest_value(series: List[Dict], end_idx: int, key: str):
    for i in range(end_idx, max(-1, end_idx - 24), -1):
        v = series[i].get(key)
        if v is not None:
            return float(v)
    return None


def _window_range(series: List[Dict], end_idx: int, key: str, hours: int):
    start = max(0, end_idx - hours + 1)
    vals = [float(e[key]) for e in series[start:end_idx + 1] if e.get(key) is not None]
    if not vals:
        return None, None
    return round(min(vals), 4), round(max(vals), 4)


def summarise_cell(cell_id: str, series: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reduce one cell's hourly series to a condition summary."""
    if not series:
        return {"cell_id": cell_id, "available": False,
                "reason": "no series returned"}

    if all(e.get("synthetic") for e in series):
        return {
            "cell_id": cell_id,
            "available": False,
            "reason": ("live fetch failed - the Open-Meteo API could not be reached, "
                       "so no measurement exists for this cycle"),
        }

    end = _now_index(series)
    observed = series[:end + 1]
    if not observed:
        return {"cell_id": cell_id, "available": False,
                "reason": "no past hours in the returned series"}

    sm_min, sm_max = _window_range(series, end, "soil_moisture_0_to_7cm", 168)
    deep_min, deep_max = _window_range(series, end, "soil_moisture_7_to_28cm", 168)

    return {
        "cell_id": cell_id,
        "available": True,
        "observed_at": series[end]["time"],
        "rainfall_1h_mm": _sum_window(series, end, 1),
        **{k: _sum_window(series, end, h) for k, h in WINDOWS.items()},
        "soil_moisture_0_to_7cm": _latest_value(series, end, "soil_moisture_0_to_7cm"),
        "soil_moisture_7_to_28cm": _latest_value(series, end, "soil_moisture_7_to_28cm"),
        "soil_moisture_0_to_7cm_7d_min": sm_min,
        "soil_moisture_0_to_7cm_7d_max": sm_max,
        "soil_moisture_7_to_28cm_7d_min": deep_min,
        "soil_moisture_7_to_28cm_7d_max": deep_max,
        "temperature_2m": _latest_value(series, end, "temperature_2m"),
        "rainfall_next_24h_mm": _sum_window(series, min(len(series) - 1, end + 24), 24),
        "hours_observed": len(observed),
    }


async def fetch_live_conditions(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Live rainfall + soil moisture for every cell, one entry per cell."""
    from weather_service import fetch_24h_forecast

    response = await fetch_24h_forecast(cells)
    data = response.get("data", {})

    conditions = {}
    for cell in cells:
        cid = cell.get("location_id")
        conditions[cid] = summarise_cell(cid, data.get(cid, []))

    live_count = sum(1 for c in conditions.values() if c.get("available"))
    return {
        "generated_at": datetime.now(IST).isoformat(),
        "source": response.get("source", "Open-Meteo"),
        "resolution": response.get("resolution", "9km"),
        "variables": ["precipitation", "soil_moisture_0_to_7cm",
                      "soil_moisture_7_to_28cm", "temperature_2m"],
        "cells_live": live_count,
        "cells_total": len(cells),
        "conditions": conditions,
    }