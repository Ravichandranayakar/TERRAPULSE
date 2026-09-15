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

    rainfall_24h = sum_precip(24)
    rainfall_3d = rainfall_24h * 2.5   # approximate 3-day from 24h series
    rainfall_7d = rainfall_24h * 5.0   # approximate 7-day

    return {
        "rainfall_24h_mm": rainfall_24h,
        "rainfall_3d_mm": rainfall_3d,
        "rainfall_7d_mm": rainfall_7d,
        "rainfall_intensity": sum_precip(1),      # last 1h as intensity proxy
        "rainfall_1h": sum_precip(1),
        "rainfall_6h": sum_precip(6),
    }


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
        "cells": []
    }

    for cell in cells:
        cell_id = cell.get("location_id")
        cell_forecast = weather_data.get(cell_id, [])

        # Extract precipitation series; limit to 24 hours
        precip_series = [float(entry.get("precipitation", 0.0)) for entry in cell_forecast[:24]]
        if not precip_series:
            logger.warning(f"[Forecast] No precipitation data for cell {cell_id} — skipping")
            continue

        horizon = len(precip_series)
        predictions = []

        for i in range(horizon):
            temporal = compute_temporal_features(precip_series, i)

            # Build the feature dict using the EXACT keys predict_risk() expects
            model_features = {
                # Terrain (static per cell)
                "slope_angle":          float(cell.get("slope_angle", 28.0) or 28.0),
                "elevation_m":          float(cell.get("elevation_m", 1500.0) or 1500.0),
                "base_susceptibility":  float(cell.get("base_susceptibility", 0.5) or 0.5),
                "historical_events":    int(cell.get("historical_count", 0) or 0),
                "road_proximity_km":    0.5 if cell.get("near_nh10") else 3.0,
                "distance_to_fault_km": 8.0,
                "ndvi":                 0.55,

                # Dynamic rainfall features from forecast
                "rainfall_24h_mm":      temporal["rainfall_24h_mm"],
                "rainfall_3d_mm":       temporal["rainfall_3d_mm"],
                "rainfall_7d_mm":       temporal["rainfall_7d_mm"],
                "rainfall_intensity":   temporal["rainfall_intensity"],

                # Soil moisture estimated from accumulated rainfall
                "soil_moisture_index":  min(0.3 + temporal["rainfall_24h_mm"] * 0.005, 0.95),
            }

            try:
                risk_output = predict_risk(model_features, model_bundle=model_bundle)
            except Exception as e:
                logger.error(f"[Forecast] predict_risk failed for cell {cell_id} hour {i}: {e}")
                risk_output = {"risk_score": 0.0, "risk_level": "low", "probability": 0.0, "contributing_factors": []}

            predictions.append({
                "timestamp":       cell_forecast[i].get("time", ""),
                "risk_score":      round(float(risk_output.get("risk_score", 0)), 1),
                "risk_level":      risk_output.get("risk_level", "low"),
                "probability":     round(float(risk_output.get("probability", 0)), 3),
                "precipitation_mm": precip_series[i],
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
