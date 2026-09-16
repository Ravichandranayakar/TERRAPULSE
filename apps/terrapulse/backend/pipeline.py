"""
TerraPulse.ai - the pipeline, stage by stage, ingestion through to the map.

    apps/terrapulse/backend/pipeline.py     <-- this file

It runs the seven stages, then hands over to the runtime inference path:

    01 DATA INGESTION       APIs, rasters, CSV, GeoJSON, Shapefile
    02 DATA PREPROCESSING   cleaning, missing values, scaling, geo-alignment
    03 GEO PROCESSING       DEM derivatives, gridding, reprojection, correlation
    04 FEATURE ENGINEERING  spatial features + temporal features -> feature matrix
    05 AI / ML MODEL        train, validate, inference
    06 RISK ENGINE          probability, score 0-100, LOW/MODERATE/HIGH/CRITICAL
    07 SERVE & VISUALIZE    FastAPI, spatial database (PostGIS), React, alerts

    FEEDBACK LOOP           new events -> curator -> curated dataset -> retrain
                            -> validate -> new version -> better predictions

    RUNTIME INFERENCE PATH  live data -> features -> loaded model -> risk map

Run it:

    python pipeline.py                  full pipeline, human readable
    python pipeline.py --json           machine readable
    python pipeline.py --stages 01,04   selected stages
    python pipeline.py --live           only the runtime inference path
    python pipeline.py --feedback       check/run the feedback loop

What is real here, stated once so it is not overclaimed
  Stages 01-07 and the runtime path are implemented and run on a timer. The
  feedback loop is implemented and scheduled; it promotes a retrained model only
  when the candidate clears a validation gate against the version serving now.
"""

import argparse
import io
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger("pipeline")

ROOT = os.path.join(REPO, "TERRAPULSE_DATA")


@dataclass
class StageResult:
    stage: str
    name: str
    status: str            # ok | partial | skipped | failed
    detail: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    def line(self) -> str:
        return "  %s %-22s %-8s %s" % (
            self.stage, self.name, self.status.upper(),
            json.dumps(self.detail, default=str)[:150])


def _stages_for_cells() -> List[Dict[str, Any]]:
    from regions import get_region_data
    return get_region_data("ner_india").get("grid_cells", [])


# ---------------------------------------------------------------------------
# 01 DATA INGESTION
# ---------------------------------------------------------------------------

def stage_01_ingestion(with_satellite: bool = True) -> StageResult:
    started = time.time()
    detail: Dict[str, Any] = {"sources": {}}

    # --- static archives on disk ---
    checks = {
        "terrain_dem": (os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "raw"), "*.tif"),
        "landcover": (os.path.join(ROOT, "08_LANDCOVER", "ESA_WorldCover", "2021_v200", "raw"), "*.tif"),
        "soil": (os.path.join(ROOT, "06_SOIL", "SoilGrids", "raw"), "*.tif"),
        "rainfall_imd": (os.path.join(ROOT, "04_RAINFALL", "IMD_RF25", "rainfall"), "*.nc"),
        "landslide_labels": (os.path.join(ROOT, "01_LANDSLIDE_LABELS"), "*.geojson"),
    }
    import glob
    for key, (directory, pattern) in checks.items():
        files = glob.glob(os.path.join(directory, "**", pattern), recursive=True)
        detail["sources"][key] = {"files": len(files), "present": bool(files)}

    # --- live API: rainfall + soil moisture ---
    from live_conditions import fetch_live_conditions
    import asyncio
    conditions = asyncio.run(fetch_live_conditions(_stages_for_cells()))
    detail["sources"]["open_meteo_live"] = {
        "present": conditions["cells_live"] > 0,
        "cells_live": conditions["cells_live"],
        "cells_total": conditions["cells_total"],
        "variables": conditions["variables"],
        "source": conditions["source"],
    }

    # --- satellite index (STAC) ---
    if with_satellite:
        try:
            import satellite_ingest
            scenes = satellite_ingest.available_scenes(_stages_for_cells()[:2], days_back=30)
            s2 = [s for s in scenes["sentinel2"].values() if isinstance(s, list)]
            s1 = [s for s in scenes["sentinel1"].values() if isinstance(s, list)]
            detail["sources"]["sentinel"] = {
                "present": bool(s2 or s1),
                "index": "Earth Search STAC v1 (keyless)",
                "s2_cells_with_scene": sum(1 for s in s2 if s),
                "s1_cells_with_scene": sum(1 for s in s1 if s),
                "newest_s2": (s2[0][0]["datetime"] if s2 and s2[0] else None),
                "newest_s1": (s1[0][0]["datetime"] if s1 and s1[0] else None),
            }
        except Exception as error:
            detail["sources"]["sentinel"] = {"present": False, "error": str(error)}

    # --- OSM ---
    osm = glob.glob(os.path.join(ROOT, "09_INFRASTRUCTURE", "OSM", "extracted", "*.shp"))
    detail["sources"]["openstreetmap"] = {"files": len(osm), "present": bool(osm)}

    present = sum(1 for s in detail["sources"].values() if s.get("present"))
    total = len(detail["sources"])
    detail["formats_ingested"] = ["API", "Raster", "CSV", "GeoJSON", "Shapefile"]
    return StageResult("01", "DATA INGESTION",
                       "ok" if present == total else "partial", detail,
                       int((time.time() - started) * 1000))


# ---------------------------------------------------------------------------
# 02 DATA PREPROCESSING
# ---------------------------------------------------------------------------

def stage_02_preprocessing() -> StageResult:
    started = time.time()
    detail: Dict[str, Any] = {}

    # The training table produced by the extract/merge chain.
    dataset = os.path.join(ROOT, "13_MODEL_DATASETS", "landslide_dataset_v0.1.csv")
    if os.path.exists(dataset):
        import pandas as pd
        df = pd.read_csv(dataset)
        positives = int((df["landslide"] == 1).sum())
        detail["training_table"] = {
            "path": os.path.relpath(dataset, REPO),
            "rows": int(len(df)),
            "columns": int(df.shape[1]),
            "positives": positives,
            "negatives": int((df["landslide"] == 0).sum()),
            "duplicate_rows": int(df.duplicated().sum()),
            "missing_cells": int(df.isna().sum().sum()),
        }
    else:
        detail["training_table"] = {"path": dataset, "present": False}

    detail["cleaning_applied"] = [
        "IMD fill value -999 set to NaN; all-zero blocks flagged as source gaps",
        "Copernicus DEM ocean/void (elevation <= 0) flagged, not silently kept",
        "WorldCover nodata class 0 excluded from class shares",
        "SoilGrids zero treated as nodata; clay+sand+silt verified to sum ~1000 g/kg",
        "median imputation fitted inside each training fold, never across the split",
        "miss_rain_clim / miss_soil indicator columns preserve what was imputed",
    ]
    detail["scaling"] = ("StandardScaler and OneHotEncoder live inside the saved "
                         "Pipeline, so training and inference apply the identical transform")
    return StageResult("02", "DATA PREPROCESSING", "ok", detail,
                       int((time.time() - started) * 1000))


# ---------------------------------------------------------------------------
# 03 GEO PROCESSING
# ---------------------------------------------------------------------------

def _source_staleness() -> List[str]:
    """Which source datasets moved since the cell features were written."""
    scripts = os.path.join(REPO, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import terrapulse_sources as sources

    artifact = os.path.join(HERE, "data", "ner_cell_features.json")
    recorded: Dict[str, Any] = {}
    if os.path.exists(artifact):
        with io.open(artifact, encoding="utf-8") as fh:
            recorded = json.load(fh).get("sources") or {}
    return sources.changed_sources(recorded, sources.source_signature())


def _rebuild_cell_features() -> bool:
    """Rerun the extractor. True when the artifact was rewritten."""
    extractor = os.path.join(REPO, "scripts", "extract_cell_features.py")
    if not os.path.exists(extractor):
        return False
    proc = subprocess.run([sys.executable, extractor], cwd=REPO,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        logger.error("cell feature rebuild failed: %s", " / ".join(tail))
        return False
    return True


def stage_03_geo(refresh: bool = True) -> StageResult:
    started = time.time()
    detail: Dict[str, Any] = {}

    stale = _source_staleness()
    detail["sources_moved"] = stale
    rebuilt = False
    if stale and refresh:
        rebuilt = _rebuild_cell_features()
    elif stale:
        detail["stale_note"] = ("--no-refresh given; the numbers below "
                                "still describe the previous release")
    detail["cell_features_rebuilt"] = rebuilt

    cells = os.path.join(HERE, "data", "ner_cell_features.json")
    if os.path.exists(cells):
        with io.open(cells, encoding="utf-8") as fh:
            artifact = json.load(fh)
        detail["cell_features"] = {
            "path": os.path.relpath(cells, REPO),
            "generated_at": artifact.get("generated_at"),
            "cells": len(artifact["cells"]),
        }
        sample = next(iter(artifact["cells"].values()))
        detail["derivatives_example"] = {
            "cell": sample["name"],
            "elevation_m": sample["static_features"]["elevation_m"],
            "slope_deg": sample["static_features"]["slope_deg"],
            "curvature_1pm": sample["static_features"]["curvature_1pm"],
            "tri_m": sample["static_features"]["tri_m"],
            "dem_tile": sample["provenance"]["dem_tile"],
        }
    detail["operations"] = [
        "DEM read per tile; gradients use true ground spacing corrected for latitude",
        "slope + aspect from arctan of the gradient magnitude",
        "curvature as map-plane Laplacian (1/m); TRI as Riley 3x3 ruggedness",
        "distances measured in local AEQD projection so metres are true metres",
        "aspect encoded as sin/cos so 359 deg and 1 deg are adjacent",
    ]
    return StageResult("03", "GEO PROCESSING", "ok", detail,
                       int((time.time() - started) * 1000))


# ---------------------------------------------------------------------------
# 04 FEATURE ENGINEERING
# ---------------------------------------------------------------------------

def stage_04_features() -> StageResult:
    started = time.time()
    from risk.trained_predictor import TrainedMLRiskPredictor, required_features
    predictor = TrainedMLRiskPredictor()

    with io.open(os.path.join(HERE, "data", "ner_cell_features.json"), encoding="utf-8") as fh:
        artifact = json.load(fh)

    required = required_features(predictor._artifact.schema)
    spatial = ["elevation_m", "slope_deg", "curvature_1pm", "tri_m", "aspect_sin",
               "aspect_cos", "landcover_class", "clay_gkg", "sand_gkg", "silt_gkg",
               "dist_road_m", "dist_river_m", "dist_water_m"]
    temporal_live = ["rainfall_1h_mm", "rainfall_24h_mm", "rainfall_3d_mm", "rainfall_7d_mm",
                     "soil_moisture_0_to_7cm", "soil_moisture_7_to_28cm"]
    climatology = ["rain_clim_annual_mm", "rain_clim_monsoon_mm",
                   "rain_clim_max1d_mm", "rain_clim_max5d_mm"]

    detail = {
        "feature_matrix": {"rows": len(artifact["cells"]), "columns": len(required)},
        "spatial_features": [f for f in spatial if f in required],
        "temporal_features_live": temporal_live,
        "climatology_features": climatology,
        "feature_source": "scripts/extract_cell_features.py -> data/ner_cell_features.json",
        "note": ("Antecedent rainfall windows are summed from 7 days of measured hourly "
                 "data. The model consumes rainfall CLIMATOLOGY; live rainfall drives the "
                 "trigger layer and is never written into a climatology column."),
    }
    missing = [f for f in required if f not in artifact["cells"][next(iter(artifact["cells"]))]["static_features"]
               and f != "road_fclass"]
    detail["features_without_a_source"] = missing
    return StageResult("04", "FEATURE ENGINEERING",
                       "ok" if not missing else "partial", detail,
                       int((time.time() - started) * 1000))


# ---------------------------------------------------------------------------
# 05 AI / ML MODEL
# ---------------------------------------------------------------------------

def stage_05_model() -> StageResult:
    started = time.time()
    from risk.trained_predictor import TrainedMLRiskPredictor, model_dir
    import feedback_loop

    predictor = TrainedMLRiskPredictor()
    metrics = feedback_loop.read_metrics(model_dir())
    reg = feedback_loop.load_registry()

    detail = {
        "active_version": (reg.get("active") or os.path.basename(model_dir())),
        "artifact_dir": os.path.relpath(model_dir(), REPO),
        "algorithm": predictor.name,
        "feature_count": len(predictor.features),
        "alert_cut": predictor.alert_cut,
        "metrics_loso": feedback_loop.loso_scores(metrics),
        "registry_versions": len(reg.get("versions", [])),
    }
    block = (metrics.get("block_cv") or {}).get(predictor.name)
    if isinstance(block, dict):
        detail["block_cv_summary"] = block.get("summary", block)
    return StageResult("05", "AI / ML MODEL", "ok", detail,
                       int((time.time() - started) * 1000))


# ---------------------------------------------------------------------------
# 06 RISK ENGINE
# ---------------------------------------------------------------------------

def stage_06_risk_engine() -> StageResult:
    started = time.time()
    import asyncio
    import live_pipeline

    payload = asyncio.run(live_pipeline.run_cycle(store=False))
    levels = [c["alert"]["alert_level"] for c in payload["cells"]]
    detail = {
        "cells_scored": len(payload["cells"]),
        "alert_distribution": {lvl: levels.count(lvl) for lvl in sorted(set(levels))},
        "outputs": ["probability 0-1", "risk score 0-100",
                    "LOW / MODERATE / HIGH / CRITICAL"],
        "components": {
            "susceptibility": "trained model, terrain-driven, stable hour to hour",
            "trigger": "live rainfall thresholds, moves every cycle",
            "combination": "alert = higher of the two; escalates when both are high",
        },
        "inference_ms_per_cycle": payload["duration_ms"],
    }
    return StageResult("06", "RISK ENGINE", "ok", detail,
                       int((time.time() - started) * 1000))


# ---------------------------------------------------------------------------
# 07 SERVE & VISUALIZE
# ---------------------------------------------------------------------------

def stage_07_serve(store: bool = True) -> StageResult:
    started = time.time()
    import asyncio
    import live_pipeline
    import spatial_db

    payload = live_pipeline.latest() or asyncio.run(live_pipeline.run_cycle(store=store))

    postgis = spatial_db.status()
    serving: Dict[str, Any] = {
        "rest_api": {"framework": "FastAPI", "live_endpoints": [
            "/api/live/conditions", "/api/live/risk", "/api/live/refresh", "/api/live/status"],
            "risk_endpoints": ["/api/risk/model-status", "/api/risk/predict-trained"]},
        "web_app": {"framework": "React + MapLibre GL", "dev_server": "vite :5173"},
        "sqlite": {"tables": ["monitoring_locations", "rainfall_observations",
                              "risk_predictions", "landslide_warnings",
                              "field_verifications"]},
    }

    if postgis.get("available"):
        spatial_db.ensure_schema()
        cells = spatial_db.upsert_cells(_stages_for_cells())
        import geo_data
        slides = spatial_db.upsert_historical_landslides(geo_data.HISTORICAL_LANDSLIDES)
        written = spatial_db.write_cycle(payload, model_version=None)
        near = spatial_db.cells_within_metres_of_landslides(25000)
        serving["postgis"] = {
            "available": True,
            "postgis_version": postgis.get("postgis_version"),
            "cells_written": cells.get("written"),
            "landslides_written": slides.get("written"),
            "observations_written": written.get("written"),
            "spatial_query_check": "%d cells within 25 km of a recorded landslide"
                                   % len(near.get("results", [])),
        }
    else:
        serving["postgis"] = {"available": False, "reason": postgis.get("reason")}

    if store:
        live_pipeline._persist(payload)
        serving["sqlite"]["cycle_persisted"] = True

    return StageResult("07", "SERVE & VISUALIZE", "ok", serving,
                       int((time.time() - started) * 1000))


# ---------------------------------------------------------------------------
# runtime inference path
# ---------------------------------------------------------------------------

def runtime_inference_path() -> StageResult:
    """Live data -> features -> loaded model -> risk map. The operational flow."""
    started = time.time()
    import asyncio
    import live_pipeline

    payload = asyncio.run(live_pipeline.run_cycle(store=True))
    return StageResult("RT", "RUNTIME INFERENCE", "ok", {
        "live_data": payload["live"]["source"],
        "cells_live": payload["live"]["cells_live"],
        "model_status": payload["model"]["status"],
        "total_ms": payload["duration_ms"],
        "output": "risk map + alerts updated",
    }, int((time.time() - started) * 1000))


STAGE_FUNCTIONS: Dict[str, Callable[..., StageResult]] = {
    "01": stage_01_ingestion,
    "02": stage_02_preprocessing,
    "03": stage_03_geo,
    "04": stage_04_features,
    "05": stage_05_model,
    "06": stage_06_risk_engine,
    "07": stage_07_serve,
}


def run_pipeline(stages: Optional[List[str]] = None,
                 with_satellite: bool = True,
                 store: bool = True,
                 refresh_cell_features: bool = True) -> Dict[str, Any]:
    """Run the pipeline. Returns every stage result plus a summary."""
    selected = stages or list(STAGE_FUNCTIONS)
    results: List[StageResult] = []

    for key in selected:
        fn = STAGE_FUNCTIONS.get(key)
        if fn is None:
            continue
        try:
            if key == "01":
                results.append(fn(with_satellite=with_satellite))
            elif key == "07":
                results.append(fn(store=store))
            elif key == "03":
                results.append(fn(refresh=refresh_cell_features))
            else:
                results.append(fn())
        except Exception as error:
            logger.exception("stage %s failed", key)
            results.append(StageResult(key, key, "failed", {"error": str(error)}, 0))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stages": [asdict(r) for r in results],
        "ok": all(r.status in ("ok", "partial", "skipped") for r in results),
    }


def run_feedback(force: bool = False) -> Dict[str, Any]:
    import feedback_loop
    return feedback_loop.run_feedback_cycle(force=force)


def main() -> int:
    parser = argparse.ArgumentParser(description="TerraPulse pipeline")
    parser.add_argument("--stages", default="", help="e.g. 01,04 (default: all)")
    parser.add_argument("--json", action="store_true", help="machine readable")
    parser.add_argument("--live", action="store_true", help="runtime inference path only")
    parser.add_argument("--feedback", action="store_true", help="run the feedback loop")
    parser.add_argument("--force-retrain", action="store_true",
                        help="retrain even when the loop is not due")
    parser.add_argument("--no-satellite", action="store_true")
    parser.add_argument("--no-refresh", action="store_true",
                        help="do not rebuild cell features when a source has moved")
    args = parser.parse_args()

    if args.feedback:
        report = run_feedback(force=args.force_retrain)
        print(json.dumps(report, indent=2, default=str) if args.json else report)
        return 0

    if args.live:
        result = runtime_inference_path()
        print(json.dumps(asdict(result), indent=2, default=str) if args.json else result.line())
        return 0

    stages = [s.strip() for s in args.stages.split(",") if s.strip()] or None
    report = run_pipeline(stages=stages, with_satellite=not args.no_satellite,
                          refresh_cell_features=not args.no_refresh)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["ok"] else 1

    print()
    print("  TerraPulse.ai pipeline - ingestion through to the map")
    print("  " + "-" * 74)
    for stage in report["stages"]:
        detail = json.dumps(stage["detail"], default=str)
        if len(detail) > 150:
            detail = detail[:147] + "..."
        print("  %s %-22s %-8s %s" % (stage["stage"], stage["name"],
                                      stage["status"].upper(), detail))
    print("  " + "-" * 74)
    total = sum(s["duration_ms"] for s in report["stages"])
    print("  %d stages | %d ms total | ok=%s"
          % (len(report["stages"]), total, report["ok"]))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())