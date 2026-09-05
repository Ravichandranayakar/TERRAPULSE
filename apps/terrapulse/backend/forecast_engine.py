import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
from ml_engine import predict_risk
from weather_service import fetch_24h_forecast

logger = logging.getLogger(__name__)

def compute_temporal_features(precip_series: List[float], current_hour_idx: int) -> Dict[str, float]:
    """
    Calculates antecedent temporal features based on a rolling sequence of hourly rainfall.
    """
    def sum_precip(hours_back: int) -> float:
        start_idx = max(0, current_hour_idx - hours_back + 1)
        return sum(precip_series[start_idx:current_hour_idx + 1])

    return {
        "rainfall_1h": sum_precip(1),
        "rainfall_3h": sum_precip(3),
        "rainfall_6h": sum_precip(6),
        "rainfall_24h": sum_precip(24)
    }

async def generate_24h_forecast(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Orchestrates the entire 24-hour predictive risk pipeline.
    """
    forecast_response = await fetch_24h_forecast(cells)
    weather_data = forecast_response.get("data", {})
    source = forecast_response.get("source", "Unknown")

    now_iso = datetime.now(timezone.utc).isoformat()
    
    result = {
        "generated_at": now_iso,
        "forecast_horizon_hours": 24,
        "forecast_source": source,
        "cells": []
    }

    for cell in cells:
        cell_id = cell.get('location_id')
        cell_forecast = weather_data.get(cell_id, [])
        
        precip_series = [entry.get("precipitation", 0.0) for entry in cell_forecast]
        predictions = []
        horizon = min(24, len(precip_series))
        
        for i in range(horizon):
            temporal_features = compute_temporal_features(precip_series, i)
            
            model_features = {
                "elevation": cell.get("elevation", 1500),
                "slope": cell.get("slope", 30),
                "distance_to_fault": cell.get("distance_to_fault", 50),
                "soil_moisture": 0.5 + (temporal_features["rainfall_24h"] * 0.001),
                "rainfall_24h": temporal_features["rainfall_24h"],
                "historical_events": cell.get("historical_count", 0)
            }
            
            risk_output = predict_risk(model_features, model_bundle=None)
            
            predictions.append({
                "timestamp": cell_forecast[i].get("time"),
                "risk_score": risk_output.get("risk_score"),
                "risk_level": risk_output.get("risk_level"),
                "precipitation_mm": precip_series[i]
            })
            
        result["cells"].append({
            "cell_id": cell_id,
            "geometry": {
                "lat_min": cell.get("lat_min"),
                "lat_max": cell.get("lat_max"),
                "lon_min": cell.get("lon_min"),
                "lon_max": cell.get("lon_max")
            },
            "predictions": predictions
        })
        
    return result
