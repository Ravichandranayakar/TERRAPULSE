import io
import json
import math
import os

from geo_data import NER_GRID_CELLS, NH10_ROUTE, EVACUATION_ROUTES, HISTORICAL_LANDSLIDES, INFRASTRUCTURE as NER_INFRA
from nepal_data import get_nepal_data

HERE = os.path.dirname(os.path.abspath(__file__))
CELL_FEATURES = os.path.join(HERE, "data", "ner_cell_features.json")

_ASPECT_POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
_terrain_cache = {"mtime": None, "cells": {}}


def _derived_terrain():
    """Terrain for the monitoring cells, read from the DEM artifact.

    geo_data carries hand-typed elevation and slope for display, and those numbers
    drift from the DEM the model actually reads. Wherever the extracted artifact
    exists its values replace them, so the map and the model describe the same
    ground. The typed values remain the fallback when the artifact is absent, so
    the map never loses terrain entirely.
    """
    if not os.path.exists(CELL_FEATURES):
        return {}
    mtime = os.path.getmtime(CELL_FEATURES)
    if _terrain_cache["mtime"] == mtime:
        return _terrain_cache["cells"]

    try:
        with io.open(CELL_FEATURES, encoding="utf-8") as fh:
            artifact = json.load(fh)
    except (OSError, ValueError):
        return {}

    derived = {}
    for cell_id, cell in (artifact.get("cells") or {}).items():
        features = cell.get("static_features") or {}
        entry = {}
        if features.get("elevation_m") is not None:
            entry["elevation_m"] = int(round(float(features["elevation_m"])))
        if features.get("slope_deg") is not None:
            entry["slope_angle"] = round(float(features["slope_deg"]), 1)
        sin_v, cos_v = features.get("aspect_sin"), features.get("aspect_cos")
        if sin_v is not None and cos_v is not None:
            bearing = math.degrees(math.atan2(sin_v, cos_v)) % 360.0
            entry["aspect"] = _ASPECT_POINTS[int((bearing + 22.5) // 45) % 8]
            entry["aspect_deg"] = round(bearing, 1)
        if entry:
            entry["terrain_source"] = "Copernicus DEM GLO-30"
            derived[cell_id] = entry

    _terrain_cache["mtime"] = mtime
    _terrain_cache["cells"] = derived
    return derived


def get_ner_data():
    derived = _derived_terrain()
    cells = [dict(cell, **derived[cell["location_id"]])
             if cell.get("location_id") in derived else dict(cell)
             for cell in NER_GRID_CELLS]
    return {
        "grid_cells": cells,
        "nh10_route": NH10_ROUTE,
        "evacuation_routes": EVACUATION_ROUTES,
        "historical_landslides": HISTORICAL_LANDSLIDES,
        "infrastructure": NER_INFRA,
        "historical_events": HISTORICAL_LANDSLIDES,
        "region_name": "NER (India)",
        "region_id": "ner_india"
    }

def get_region_data(region_id: str):
    if region_id == 'nepal_case':
        return get_nepal_data()
    # Default to NER for SIH Demo
    return get_ner_data()
