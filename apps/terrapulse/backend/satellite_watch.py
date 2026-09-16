"""
Satellite observation layer, refreshed on its own clock.

Sentinel imagery changes every ~5-12 days, so this does not belong inside the
15-minute risk cycle: re-downloading a five-day-old scene every quarter hour is
wasted work that would add seconds to every pass. It runs here instead, as a
scheduled job, and the result is attached to each monitoring cell as an
observation the map and the API can read.

What this is not
  These values are not model inputs. The trained artifact consumes a fixed set of
  features named in its feature_schema.json, and no satellite band is among
  them. The count is not repeated here: it changed once already when the Bhuvan
  geology layers were added, and a hardcoded number went stale silently. Adding one means retraining, which is a separate decision with its own
  validation gate. So the satellite result is reported next to the model score,
  never folded into it.

Placement accuracy differs by sensor and is reported rather than smoothed over:
a Sentinel-2 window is placed from the tile's own geotransform, a Sentinel-1 GRD
window only from ground control points. See satellite_ingest.py.
"""

import io
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "data", "satellite")
LATEST_JSON = os.path.join(HERE, "data", "satellite_latest.json")

# Optical passes in the monsoon are far apart: cloud can push the newest usable
# Sentinel-2 scene well past a month. A short window silently drops the optical
# layer and leaves only SAR, so the default looks back far enough to find one.
DAYS_BACK = int(os.environ.get("TERRAPULSE_SATELLITE_DAYS_BACK", "60"))

_state: Dict[str, Any] = {"latest": None, "runs": 0, "last_error": None}


def load_latest() -> Optional[Dict[str, Any]]:
    """The most recent observation set, from memory or from disk."""
    if _state["latest"] is not None:
        return _state["latest"]
    if not os.path.exists(LATEST_JSON):
        return None
    try:
        with io.open(LATEST_JSON, encoding="utf-8") as fh:
            _state["latest"] = json.load(fh)
    except (OSError, ValueError) as error:
        logger.warning("[SatelliteWatch] could not read %s: %s", LATEST_JSON, error)
        return None
    return _state["latest"]


def observations() -> Dict[str, Any]:
    """Per-cell observations keyed by cell id. Empty when nothing has run yet."""
    return (load_latest() or {}).get("cells") or {}


def _cells() -> List[Dict[str, Any]]:
    from live_pipeline import load_cell_features

    artifact = load_cell_features()
    return [{"location_id": cid,
             "centroid_lat": cell["centroid_lat"],
             "centroid_lon": cell["centroid_lon"]}
            for cid, cell in artifact["cells"].items()]


def _refresh_blocking() -> Dict[str, Any]:
    import satellite_ingest

    cells = _cells()
    manifest = satellite_ingest.ingest(cells, OUT_DIR, days_back=DAYS_BACK)

    per_cell: Dict[str, Any] = {}
    for entry in manifest.get("cells", []):
        observation = satellite_ingest.summarise_cell(entry)
        per_cell[observation["cell_id"]] = observation

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": manifest.get("source"),
        "days_back": DAYS_BACK,
        "cells_total": len(cells),
        "cells_with_imagery": manifest.get("cells_with_imagery"),
        "images_downloaded": manifest.get("bands_downloaded"),
        "role": ("observation layer, not a model input: the trained model consumes the "
                 "fixed feature contract in its feature_schema.json and no satellite "
                 "band is among them"),
        "cells": per_cell,
    }

    os.makedirs(os.path.dirname(LATEST_JSON), exist_ok=True)
    with io.open(LATEST_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return payload


async def refresh() -> Dict[str, Any]:
    """Pull the newest usable windows for every cell. Blocking work stays off the loop."""
    import asyncio

    started = time.time()
    try:
        payload = await asyncio.get_event_loop().run_in_executor(None, _refresh_blocking)
    except Exception as error:
        _state["last_error"] = str(error)
        logger.warning("[SatelliteWatch] refresh failed: %s", error)
        raise
    payload["duration_ms"] = int((time.time() - started) * 1000)
    _state["latest"] = payload
    _state["runs"] += 1
    _state["last_error"] = None
    return payload


def status() -> Dict[str, Any]:
    """State for the dashboard, without triggering a download."""
    payload = load_latest() or {}
    return {
        "runs": _state["runs"],
        "last_error": _state["last_error"],
        "generated_at": payload.get("generated_at"),
        "days_back": payload.get("days_back"),
        "cells_with_imagery": payload.get("cells_with_imagery"),
        "cells_total": payload.get("cells_total"),
        "images_downloaded": payload.get("images_downloaded"),
        "role": payload.get("role"),
        "store": os.path.relpath(LATEST_JSON, HERE),
    }