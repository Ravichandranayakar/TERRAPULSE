import httpx
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

async def fetch_24h_forecast(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Fetches 24-hour hourly precipitation forecast from Open-Meteo.
    Uses bulk coordinate querying to avoid rate limits.
    """
    if not cells:
        return {}

    # Extract centroids for API call
    lats = [str(cell.get('centroid_lat', 0.0)) for cell in cells]
    lons = [str(cell.get('centroid_lon', 0.0)) for cell in cells]

    params = {
        "latitude": ",".join(lats),
        "longitude": ",".join(lons),
        "hourly": "precipitation",
        "forecast_days": 2,
        "timezone": "auto"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(OPEN_METEO_URL, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, dict) and "hourly" in data:
                data = [data]
            
            result = {}
            for i, cell in enumerate(cells):
                cell_id = cell.get('location_id')
                if i < len(data) and "hourly" in data[i]:
                    hourly_data = data[i]["hourly"]
                    times = hourly_data.get("time", [])
                    precip = hourly_data.get("precipitation", [])
                    
                    forecast_series = []
                    for t, p in zip(times, precip):
                        forecast_series.append({"time": t, "precipitation": p})
                    
                    result[cell_id] = forecast_series
                else:
                    result[cell_id] = []
                    
            return {
                "source": "Open-Meteo",
                "resolution": "9km",
                "data": result
            }
            
    except Exception as e:
        logger.error(f"Failed to fetch forecast from Open-Meteo: {e}")
        return {"source": "Error", "resolution": "N/A", "data": {}}
