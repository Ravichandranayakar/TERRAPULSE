import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
from ml_engine import predict_risk, load_model

logger = logging.getLogger(__name__)

# Load model bundle once at module level — reused across all forecast calls
_model_bundle = None

def _get_model():
    global _model_bundle
    if _model_bundle is None:
        _model_bundle = load_model()
    return _model_bundle


def compute_temporal_features(precip_series: List[float], current_hour_idx: int) -> Dict[str, float]:
    """
    Calculates antecedent temporal features based on a rolling sequence of hourly rainfall.
    Matches the exact feature keys expected by predict_risk() in ml_engine.py.
    """
    def sum_precip(hours_back: int) -> float:
        start_idx = max(0, current_hour_idx - hours_back + 1)
        return round(sum(precip_series[start_idx:current_hour_idx + 1]), 2)

    # Real sums over the measured series. The earlier version held only 24 hours
    # and multiplied: 3-day = 24h * 2.5, 7-day = 24h * 5.0. Those constants are
    # invented, so a single wet day produced a large "7-day total". The series
    # now carries 7 days of hourly measurement, so all three are counted.
    return {
        "rainfall_24h_mm": sum_precip(24),
        "rainfall_3d_mm": sum_precip(72),
        "rainfall_7d_mm": sum_precip(168),
        "rainfall_intensity": sum_precip(1),      # last 1h as intensity proxy
        "rainfall_1h": sum_precip(1),
        "rainfall_6h": sum_precip(6),
    }


def _soil_moisture_index(entry: Dict[str, Any], temporal: Dict[str, float]) -> float:
    """Measured volumetric soil moisture when present, else a rainfall estimate."""
    value = entry.get("soil_moisture_0_to_7cm")
    if value is not None:
        return round(min(1.0, max(0.0, float(value) / 0.50)), 4)
    return round(min(0.95, 0.3 + temporal["rainfall_24h_mm"] * 0.005), 4)


async def generate_24h_forecast(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Orchestrates the entire 24-hour predictive risk pipeline.

    For each monitoring cell:
      1. Fetches real hourly precipitation from Open-Meteo (via weather_service)
      2. Builds ML feature vectors hour-by-hour using the forecast rainfall
      3. Runs predict_risk() with the SAME loaded model bundle used by the Risk Map
      4. Returns time-stamped risk predictions (score + level) for each cell

    Result feeds the 24h Forecast page time scrubber and chart.
    """
    from weather_service import fetch_24h_forecast

    forecast_response = await fetch_24h_forecast(cells)
    weather_data = forecast_response.get("data", {})
    source = forecast_response.get("source", "Unknown")

    model_bundle = _get_model()
    now_iso = datetime.now(timezone.utc).isoformat()

    result = {
        "generated_at": now_iso,
        "forecast_horizon_hours": 24,
        "forecast_source": source,
        "live": forecast_response.get("live", {}),
        "cells": []
    }

    for cell in cells:
        cell_id = cell.get("location_id")
        cell_forecast = weather_data.get(cell_id, [])

        # Extract precipitation series; limit to 24 hours
        # The series carries 7 days of measured history followed by the forecast,
        # so the trailing windows have real data behind them. Locate the current
        # hour and iterate only over the hours still ahead.
        from live_conditions import _now_index

        now_idx = _now_index(cell_forecast)
        precip_series = [float(entry.get("precipitation", 0.0)) for entry in cell_forecast]
        future_entries = cell_forecast[now_idx + 1: now_idx + 25]
        if not precip_series:
            logger.warning(f"[Forecast] No precipitation data for cell {cell_id} — skipping")
            continue

        horizon = len(future_entries)
        predictions = []

        for i in range(horizon):
            current_idx = now_idx + 1 + i
            temporal = compute_temporal_features(precip_series, current_idx)

            # Build the feature dict using the EXACT keys predict_risk() expects
            model_features = {
                # Terrain (static per cell)
                "slope_angle":          float(cell.get("slope_angle", 28.0) or 28.0),
                "elevation_m":          float(cell.get("elevation_m", 1500.0) or 1500.0),
                "base_susceptibility":  float(cell.get("base_susceptibility", 0.5) or 0.5),
                "historical_count":    int(cell.get("historical_count", 0) or 0),
                "road_proximity_km":    0.5 if cell.get("near_nh10") else 3.0,
                "distance_to_fault_km": 8.0,
                "ndvi":                 0.55,

                # Dynamic rainfall features from forecast
                "rainfall_24h_mm":      temporal["rainfall_24h_mm"],
                "rainfall_3d_mm":       temporal["rainfall_3d_mm"],
                "rainfall_7d_mm":       temporal["rainfall_7d_mm"],
                "rainfall_intensity":   temporal["rainfall_intensity"],

                # Soil moisture estimated from accumulated rainfall
                "soil_moisture_index":  _soil_moisture_index(future_entries[i], temporal),
            }

            try:
                risk_output = predict_risk(model_features, model_bundle=model_bundle)
            except Exception as e:
                logger.error(f"[Forecast] predict_risk failed for cell {cell_id} hour {i}: {e}")
                risk_output = {"risk_score": 0.0, "risk_level": "low", "probability": 0.0, "contributing_factors": []}

            predictions.append({
                "timestamp":       future_entries[i].get("time", ""),
                "risk_score":      round(float(risk_output.get("risk_score", 0)), 1),
                "risk_level":      risk_output.get("risk_level", "low"),
                "probability":     round(float(risk_output.get("probability", 0)), 3),
                "precipitation_mm": float(future_entries[i].get("precipitation", 0.0) or 0.0),
                "soil_moisture":   model_features["soil_moisture_index"],
            })

        result["cells"].append({
            "cell_id": cell_id,
            "name": cell.get("name", cell_id),
            "geometry": {
                "lat_min": cell.get("lat_min"),
                "lat_max": cell.get("lat_max"),
                "lon_min": cell.get("lon_min"),
                "lon_max": cell.get("lon_max"),
            },
            "predictions": predictions,
        })

    return result
