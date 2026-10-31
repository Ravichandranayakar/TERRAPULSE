"""
Turn curator-approved field reports into training rows, then merge them with the
base dataset.

Why this exists
  The verification service already collects field and citizen reports and lets a
  curator mark a report "eligible for training". It builds a dataset MANIFEST
  (which report IDs went in), but the manifest was written with
  training_status="not_automatically_run" and model_updated=false. Nothing turned
  those approved reports into actual feature rows, so the feedback loop had
  nothing new to learn from.

What this does
    approved reports (SQLite)
      -> points CSV
      -> the same five extractors used for the original training points
      -> rows in the identical 56-column schema
      -> appended to landslide_dataset_v0.1.csv
      -> landslide_dataset_<version>.csv, ready to train on

Labelling
  event_presence decides the label: a report confirming an observed landslide
  becomes label 1, a report confirming NO landslide becomes label 0. Those
  observed negatives are genuinely valuable, because the original negatives were
  constructed rather than observed. A report that does not state presence is left
  out rather than guessed at.

Output
  13_MODEL_DATASETS/curated_<version>.csv        only the new rows (provenance)
  13_MODEL_DATASETS/landslide_dataset_<version>.csv   base + curated, trainable
"""

import io
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(REPO, "TERRAPULSE_DATA")
DATA_DIR = os.path.join(ROOT, "13_MODEL_DATASETS")
BASE_DATASET = os.path.join(DATA_DIR, "landslide_dataset_v0.1.csv")
BACKEND = os.path.join(REPO, "apps", "terrapulse", "backend")

sys.path.insert(0, BACKEND)

# The verification service stores event_presence as confirmed / not_observed /
# uncertain (see verification/schemas.py, EVENT_PRESENCE). The builder used to
# look for "present" / "absent", which no report ever carried, so every approved
# report was silently skipped and the "curated" dataset came out identical to the
# base. Uncertain is still left out rather than guessed at.
LABEL_BY_PRESENCE = {"confirmed": 1, "not_observed": 0}

LC_NAMES = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built",
            60: "bare", 70: "snow", 80: "water", 90: "wetland", 95: "mangrove",
            100: "moss"}


def eligible_reports(hazard_type: str = "landslide"):
    """Curator-approved reports that carry a location and a date."""
    import main as backend
    repo = backend._verification_service.repository
    return repo.get_eligible_reports(hazard_type)


def region_for_point(lat: float, lon: float):
    """State and district for a report coordinate.

    Field reports carry a GPS fix but no administrative names, and the training
    schema wants them (STATE drives leave-one-state-out validation). The monitoring
    grid is the project's own gazetteer, so a report is assigned to the cell that
    contains it, or to the nearest cell when it falls between cells.
    """
    try:
        from geo_data import NER_GRID_CELLS
    except ImportError:
        return "", ""

    best, best_d = None, None
    for cell in NER_GRID_CELLS:
        if (cell["lat_min"] <= lat <= cell["lat_max"]
                and cell["lon_min"] <= lon <= cell["lon_max"]):
            return cell.get("state", ""), cell.get("district", "")
        d = ((cell["centroid_lat"] - lat) ** 2
             + (cell["centroid_lon"] - lon) ** 2)
        if best_d is None or d < best_d:
            best, best_d = cell, d
    # ~25 km. Further out the report is outside the monitored region and is
    # better left unnamed than assigned to a cell it does not belong to.
    if best is None or best_d > 0.0625:
        return "", ""
    return best.get("state", ""), best.get("district", "")


def reports_to_points(reports, out_csv: str) -> pd.DataFrame:
    rows = []
    for report in reports:
        presence = (report.get("event_presence") or "").strip().lower()
        label = LABEL_BY_PRESENCE.get(presence)
        if label is None:
            continue
        observed = str(report.get("observed_at") or "")
        year = observed[:4] if len(observed) >= 4 and observed[:4].isdigit() else ""
        lon = float(report.get("longitude"))
        lat = float(report.get("latitude"))
        fallback_state, fallback_district = region_for_point(lat, lon)
        rows.append({
            "report_id": report.get("id"),
            "SLIDE_NO": "CURATED/%s/%s/%05d" % (
                (report.get("hazard_type") or "landslide").upper(), year or "NADA",
                int(report.get("id") or 0)),
            "STATE": report.get("state") or fallback_state,
            "DISTRICT": report.get("district") or fallback_district,
            "INITIATION": year,
            "lon": lon,
            "lat": lat,
            "landslide": label,
            "source": report.get("source_type") or "field_officer",
        })
    frame = pd.DataFrame(rows)
    frame.to_csv(out_csv, index=False)
    return frame


def run_extractors(points_csv: str, work_dir: str) -> dict:
    """Call the same five extractors used for the original training points."""
    outputs = {
        "terrain": os.path.join(work_dir, "terrain_at_points.csv"),
        "landcover": os.path.join(work_dir, "landcover_at_points.csv"),
        "soil": os.path.join(work_dir, "soil_at_points.csv"),
        "rainfall": os.path.join(work_dir, "rainfall_at_points.csv"),
        "distance": os.path.join(work_dir, "distances_at_points.csv"),
    }
    scripts = {
        "terrain": "sample_terrain_at_points.py",
        "landcover": "extract_landcover_at_points.py",
        "soil": "extract_soil_at_points.py",
        "rainfall": "extract_rainfall_at_points.py",
        "distance": "extract_distances_at_points.py",
    }
    for key, script in scripts.items():
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, script), points_csv, outputs[key]],
            cwd=HERE, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        status = "ok" if proc.returncode == 0 and os.path.exists(outputs[key]) else "FAILED"
        print("    %-10s %s" % (key, status))
        if status == "FAILED":
            print((proc.stderr or proc.stdout or "")[-600:])
    return outputs


def build_rows(points: pd.DataFrame, outputs: dict) -> pd.DataFrame:
    """Assemble curated rows in the identical 56-column training schema."""
    terrain = pd.read_csv(outputs["terrain"])
    rainfall = pd.read_csv(outputs["rainfall"])
    landcover = pd.read_csv(outputs["landcover"])
    soil = pd.read_csv(outputs["soil"])
    distance = pd.read_csv(outputs["distance"])

    merged = terrain.copy()
    for frame in (rainfall, landcover, soil, distance):
        merged = pd.concat([merged, frame.drop(columns=["SLIDE_NO"])], axis=1)

    # Every extractor repeats the identifier columns (STATE, lon, lat). Left as
    # they are they become duplicate labels, and a duplicate label makes the
    # reindex below raise. Keep the first copy of each name.
    merged = merged.loc[:, ~merged.columns.duplicated()]

    merged = merged.merge(
        points[["SLIDE_NO", "landslide", "source", "report_id"]], on="SLIDE_NO", how="left")
    if merged["landslide"].isna().any():
        raise SystemExit(
            "curated rows could not be matched back to their reports: the extractor "
            "outputs do not share a SLIDE_NO with the points file. Check that every "
            "extractor preserves the input identifier rather than renumbering it.")

    # derived columns, matching merge_landslide_features.py exactly
    merged["texture_sum_gkg"] = (merged["clay_gkg"] + merged["sand_gkg"]
                                 + merged["silt_gkg"]).round(2)
    merged["dist_road_km"] = (merged["dist_road_m"] / 1000.0).round(4)
    merged["dist_river_km"] = (merged["dist_river_m"] / 1000.0).round(4)
    merged["dist_water_km"] = (merged["dist_water_m"] / 1000.0).round(4)
    merged["low_slope_review"] = (merged["slope_deg"] < 10).astype(int)
    merged["landcover_name"] = merged["landcover_class"].map(
        lambda v: LC_NAMES.get(int(v), "unknown") if pd.notna(v) else "unknown")
    return merged


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "curated_v0.1"
    hazard_type = sys.argv[2] if len(sys.argv) > 2 else "landslide"

    print("curated dataset build: %s (%s)" % (version, hazard_type))
    reports = eligible_reports(hazard_type)
    print("  curator-approved eligible reports: %d" % len(reports))

    if not reports:
        print("  nothing approved for training yet - no dataset written")
        return 0

    work_dir = os.path.join(DATA_DIR, "curated_%s" % version)
    os.makedirs(work_dir, exist_ok=True)

    points_csv = os.path.join(work_dir, "points.csv")
    points = reports_to_points(reports, points_csv)
    if points.empty:
        print("  no report stated event presence - no dataset written")
        return 0
    print("  usable reports: %d  (landslide=%d, no-landslide=%d)"
          % (len(points), int((points.landslide == 1).sum()),
             int((points.landslide == 0).sum())))

    print("  extracting features (same five sources as training) ...")
    outputs = run_extractors(points_csv, work_dir)

    curated = build_rows(points, outputs)
    curated_path = os.path.join(DATA_DIR, "curated_%s.csv" % version)
    curated.to_csv(curated_path, index=False)
    print("  wrote %s (%d rows)" % (curated_path, len(curated)))

    base = pd.read_csv(BASE_DATASET)
    combined = pd.concat([base, curated.reindex(columns=base.columns)], ignore_index=True)
    # Base rows keep the point_id they already carry; only the appended rows
    # need one, and "cur_" cannot collide with base's "pos_"/"neg_" ids.
    combined.loc[combined.index[len(base):], "point_id"] = [
        "cur_%05d" % i for i in range(len(combined) - len(base))]

    out_path = os.path.join(DATA_DIR, "landslide_dataset_%s.csv" % version)
    combined.to_csv(out_path, index=False)

    manifest = {
        "version": version,
        "base_rows": int(len(base)),
        "curated_rows": int(len(curated)),
        "total_rows": int(len(combined)),
        "labels": {"landslide": int((combined.landslide == 1).sum()),
                   "no_landslide": int((combined.landslide == 0).sum())},
        "report_ids": [int(r) for r in points.report_id.tolist()],
        "dataset": os.path.relpath(out_path, REPO),
    }
    with io.open(os.path.join(work_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print("\nwrote %s" % out_path)
    print("  %d base + %d curated = %d rows x %d cols"
          % (len(base), len(curated), len(combined), combined.shape[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())