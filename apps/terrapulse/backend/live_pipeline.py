"""
The live cycle: sources -> features -> model -> map.

Design, stated plainly because it is easy to misread

  The trained Random Forest scores TERRAIN SUSCEPTIBILITY from features that
  describe a place - slope, elevation, soil texture, rainfall climatology, land
  cover, distance to road. Those do not change hour to hour, so its susceptibility
  score does not either. That is a property of the model, not a caching shortcut.

  Rainfall and soil moisture DO change, and they are handled by a separate,
  explicitly-labelled rainfall trigger whose thresholds come from the recorded
  conditions of the historical events in our own inventory.

  The alert on the map is the higher of the two, escalating when both are high.
  Susceptibility answers "how bad would it be here"; the trigger answers "is it
  happening now". A place can be highly susceptible and currently quiet.

What is NOT done here, deliberately
  Live rainfall is never written into the model's `rain_clim_annual_mm` slot.
  That column is a 35-year annual average. Putting today's 40 mm there makes the
  model read "a place with a 40 mm/yr climate" - it would return a number and the
  number would be meaningless. Feeding live rainfall to the model requires
  retraining on time-varying rainfall, which requires event dates we do not have.
"""

import io
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

HERE = os.path.dirname(os.path.abspath(__file__))
CELL_FEATURES = os.path.join(HERE, "data", "ner_cell_features.json")

# ---------------------------------------------------------------------------
# Rainfall trigger
#
# Bands derived from the trigger rainfall recorded against the seven historical
# Sikkim events carried in geo_data.HISTORICAL_LANDSLIDES, whose notes read:
#   3-day accumulated 210 / 280-320 / 350 mm   7-day antecedent 180 / 220 mm
#   24h 120 mm
# The ALERT band takes the lower end of those recorded ranges, so it marks the
# conditions under which a slide has actually been recorded here. WATCH is half
# of ALERT, SEVERE is 1.5x. These are operational thresholds, not a fitted model,
# and they should be re-derived when dated events become available.
# ---------------------------------------------------------------------------
TRIGGER_ALERT = {"rainfall_24h_mm": 100.0, "rainfall_3d_mm": 200.0, "rainfall_7d_mm": 180.0}
TRIGGER_ORDER = ("NONE", "WATCH", "ALERT", "SEVERE")
SUSCEPTIBILITY_ORDER = ("LOW", "MODERATE", "HIGH", "CRITICAL")
ALERT_ORDER = ("LOW", "MODERATE", "HIGH", "CRITICAL")


def classify_trigger(cond: Dict[str, Any]) -> Dict[str, Any]:
    """Rainfall/soil-moisture condition -> NONE / WATCH / ALERT / SEVERE."""
    if not cond or not cond.get("available"):
        return {"level": "UNKNOWN", "index": -1,
                "reason": cond.get("reason", "no live measurement"),
                "exceeded": []}

    ratios = {}
    for key, alert_at in TRIGGER_ALERT.items():
        value = cond.get(key)
        if value is not None:
            ratios[key] = float(value) / alert_at

    if not ratios:
        return {"level": "UNKNOWN", "index": -1, "reason": "no rainfall fields", "exceeded": []}

    peak = max(ratios.values())
    driver = max(ratios, key=ratios.get)

    if peak >= 1.5:
        level = "SEVERE"
    elif peak >= 1.0:
        level = "ALERT"
    elif peak >= 0.5:
        level = "WATCH"
    else:
        level = "NONE"

    return {
        "level": level,
        "index": TRIGGER_ORDER.index(level),
        "peak_ratio": round(peak, 3),
        "driver": driver,
        "exceeded": sorted(k for k, r in ratios.items() if r >= 1.0),
        "basis": "rainfall thresholds derived from recorded historical trigger conditions",
    }


def combine(susceptibility_class: str, trigger_index: int) -> Dict[str, Any]:
    """Final alert = higher of terrain susceptibility and live trigger."""
    sus_index = (SUSCEPTIBILITY_ORDER.index(susceptibility_class)
                 if susceptibility_class in SUSCEPTIBILITY_ORDER else 0)
    trig = max(trigger_index, 0)

    level_index = max(sus_index, trig)
    escalated = False
    if sus_index >= 2 and trig >= 2:
        level_index = 3
        escalated = True

    return {
        "alert_level": ALERT_ORDER[level_index],
        "alert_index": level_index,
        "susceptibility_component": susceptibility_class,
        "trigger_component": TRIGGER_ORDER[trig] if trig < len(TRIGGER_ORDER) else "UNKNOWN",
        "escalated_because_both_high": escalated,
        "rule": ("alert is the higher of terrain susceptibility and the live rainfall "
                 "trigger; it escalates to CRITICAL when both reach HIGH/ALERT"),
    }


def _soil_moisture_index(value: Optional[float]) -> Optional[float]:
    """m3/m3 -> 0-1 fraction of saturation, assuming 0.50 m3/m3 field capacity.

    Open-Meteo reports volumetric soil moisture in m3/m3 (typical NER monsoon
    range 0.20-0.45). The rainfall_observations column is named _index and holds
    0-1, so the value is scaled here rather than stored in mismatched units.
    """
    if value is None:
        return None
    return round(min(1.0, max(0.0, float(value) / 0.50)), 4)


def load_cell_features() -> Dict[str, Any]:
    if not os.path.exists(CELL_FEATURES):
        raise FileNotFoundError(
            "missing %s. Run scripts/extract_cell_features.py to build the static "
            "per-cell feature table for the monitoring cells." % CELL_FEATURES)
    with io.open(CELL_FEATURES, encoding="utf-8") as fh:
        return json.load(fh)


_state: Dict[str, Any] = {"latest": None, "runs": 0, "last_error": None}


def latest() -> Optional[Dict[str, Any]]:
    """Most recent completed cycle, or None if none has run yet."""
    return _state["latest"]


def _cells_for_weather(artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"location_id": cid, "centroid_lat": c["centroid_lat"],
             "centroid_lon": c["centroid_lon"]}
            for cid, c in artifact["cells"].items()]


async def run_cycle(store: bool = True) -> Dict[str, Any]:
    """One full pass: live sources -> feature vector -> model -> alert -> store."""
    started = time.time()
    artifact = load_cell_features()

    from live_conditions import fetch_live_conditions
    conditions = await fetch_live_conditions(_cells_for_weather(artifact))

    from risk.trained_predictor import (ArtifactUnavailable, TrainedMLRiskPredictor)
    from risk.schemas import TrainedRiskFeatureInput

    try:
        predictor = TrainedMLRiskPredictor()
        model_status, model_note = "available", None
    except ArtifactUnavailable as error:
        predictor = None
        model_status, model_note = "unavailable", str(error)
        logger.warning("[LivePipeline] trained artifact unavailable: %s", error)

    # Satellite is an observation layer, not a model input: the artifact consumes a
    # fixed feature contract (41 columns in v0.4). It rides along with each cell so
    # the map can show the newest usable pass next to the model score.
    try:
        import satellite_watch
        satellite_observations = satellite_watch.observations()
    except Exception as error:
        logger.warning("[LivePipeline] satellite observations unavailable: %s", error)
        satellite_observations = {}

    results = []
    for cid, cell in artifact["cells"].items():
        cond = conditions["conditions"].get(cid, {})
        trigger = classify_trigger(cond)

        model_score = None
        susceptibility = None
        factors = []
        if predictor is not None:
            vector = dict(cell["static_features"])
            vector["road_fclass"] = cell["road_fclass"]
            try:
                prediction = predictor.predict(
                    TrainedRiskFeatureInput(cell_id=cid, features=vector))
                model_score = prediction.risk_score
                susceptibility = prediction.risk_class
                factors = prediction.contributing_factors
            except Exception as error:  # a bad vector must not kill the cycle
                logger.warning("[LivePipeline] scoring failed for %s: %s", cid, error)

        combined = combine(susceptibility or "LOW", trigger["index"])

        results.append({
            "location_id": cid,
            "name": cell["name"],
            "district": cell["district"],
            "state": cell["state"],
            "centroid_lat": cell["centroid_lat"],
            "centroid_lon": cell["centroid_lon"],
            "susceptibility_score": model_score,
            "susceptibility_class": susceptibility,
            "trigger": trigger,
            "alert": combined,
            "conditions": cond,
            "contributing_factors": factors,
            "road_fclass": cell["road_fclass"],
            "satellite": satellite_observations.get(cid),
            "provenance": cell["provenance"],
        })

    payload = {
        "generated_at": datetime.now(IST).isoformat(),
        "duration_ms": int((time.time() - started) * 1000),
        "model": {
            "status": model_status,
            "note": model_note,
            "features": (predictor.features if predictor else None),
            "alert_cut": (predictor.alert_cut if predictor else None),
            "meaning": ("terrain susceptibility - how prone this place is. It does not "
                        "change hour to hour because slope and soil texture do not."),
        },
        "live": {
            "source": conditions["source"],
            "cells_live": conditions["cells_live"],
            "cells_total": conditions["cells_total"],
            "meaning": ("measured rainfall and soil moisture. This is what changes "
                        "every cycle."),
        },
        "cells": results,
    }

    if store:
        try:
            _persist(payload)
        except Exception as error:
            logger.warning("[LivePipeline] persistence failed: %s", error)

    _state["latest"] = payload
    _state["runs"] += 1
    _state["last_error"] = None
    logger.info("[LivePipeline] cycle %d done in %d ms (%d/%d cells live)",
                _state["runs"], payload["duration_ms"],
                conditions["cells_live"], conditions["cells_total"])
    return payload


def _persist(payload: Dict[str, Any]) -> None:
    """Write this cycle into risk_predictions + rainfall_observations."""
    import main as backend

    conn = backend._get_db()
    try:
        for cell in payload["cells"]:
            cond = cell["conditions"] or {}
            if cond.get("available"):
                conn.execute("""
                    INSERT INTO rainfall_observations
                    (location_id, timestamp, rainfall_24h_mm, rainfall_3d_mm,
                     rainfall_7d_mm, rainfall_intensity, soil_moisture_index)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    cell["location_id"], payload["generated_at"],
                    cond.get("rainfall_24h_mm") or 0.0,
                    cond.get("rainfall_3d_mm") or 0.0,
                    cond.get("rainfall_7d_mm") or 0.0,
                    cond.get("rainfall_1h_mm") or 0.0,
                    _soil_moisture_index(cond.get("soil_moisture_0_to_7cm")),
                ))

            if cell["susceptibility_score"] is None:
                continue
            conn.execute("""
                INSERT INTO risk_predictions
                (location_id, timestamp, risk_score, risk_level, probability,
                 contributing_factors)
                VALUES (?,?,?,?,?,?)
            """, (
                cell["location_id"], payload["generated_at"],
                cell["susceptibility_score"],
                (cell["alert"]["alert_level"] or "low").lower(),
                cell["susceptibility_score"] / 100.0,
                json.dumps({
                    "source": "trained_model_live_cycle",
                    "susceptibility_class": cell["susceptibility_class"],
                    "trigger_level": cell["trigger"]["level"],
                    "top_factors": cell["contributing_factors"],
                }),
            ))
        conn.commit()
    finally:
        conn.close()