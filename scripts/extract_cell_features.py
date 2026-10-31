"""
Extract the exact feature vector the trained model expects, at the 10 fixed
NER monitoring-cell centroids used by the Risk Map.

Why this exists
  The trained model (models/landslide_v0.4, LightGBM) consumes terrain,
  rainfall-climatology, soil, land-cover, distance and Bhuvan geomorphology
  and lineament features - the same columns scripts/extract_*.py and
  scripts/bhuvan_fetch_points.py produced for the 17,092 training points. The
  10 map cells were never part of that table, so the live pipeline had nothing
  valid to hand the model and the map fell back to a hand-written rule score.

  This closes that gap by running the SAME extraction logic at the cell
  centroids, so the map can call the real model instead of a stand-in.

Static by nature, not by caching
  Slope, elevation, soil texture and rainfall climatology describe a place.
  They are rebuilt whenever the underlying source is republished - a new DEM
  version, a new WorldCover year, more IMD years - not re-derived every cycle.
  Rainfall and soil moisture DO change hourly and come from the live pipeline.

Output
  apps/terrapulse/backend/data/ner_cell_features.json
"""

import csv
import glob
import importlib.util
import json
import math
import os
import sys
import time

import numpy as np
import rasterio
from rasterio.windows import Window

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(REPO, "TERRAPULSE_DATA")
BACKEND = os.path.join(REPO, "apps", "terrapulse", "backend")
OUT_JSON = os.path.join(BACKEND, "data", "ner_cell_features.json")

sys.path.insert(0, HERE)
from terrapulse_sources import source_signature


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stp = _load("sample_terrain_at_points")    # derive(), meters_per_degree()
rfp = _load("extract_rainfall_at_points")  # year_files(), summarise()

sys.path.insert(0, BACKEND)
import geo_data  # noqa: E402

CELLS = geo_data.NER_GRID_CELLS

BUFFER_M = 500.0
LC_CLASSES = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built",
              60: "bare", 70: "snow", 80: "water", 90: "wetland", 100: "moss"}
LC_PCT = ["lc_tree_pct", "lc_shrub_pct", "lc_grass_pct", "lc_crop_pct",
          "lc_built_pct", "lc_bare_pct", "lc_snow_pct", "lc_water_pct",
          "lc_wetland_pct", "lc_moss_pct"]
LC_CODE = {"lc_tree_pct": 10, "lc_shrub_pct": 20, "lc_grass_pct": 30,
           "lc_crop_pct": 40, "lc_built_pct": 50, "lc_bare_pct": 60,
           "lc_snow_pct": 70, "lc_water_pct": 80, "lc_wetland_pct": 90,
           "lc_moss_pct": 100}

SOIL_SPEC = [("clay_gkg", "clay_0-5cm_mean.tif", 1.0),
             ("sand_gkg", "sand_0-5cm_mean.tif", 1.0),
             ("silt_gkg", "silt_0-5cm_mean.tif", 1.0),
             ("bulk_density_kgdm3", "bdod_0-5cm_mean.tif", 100.0),
             ("soc_gkg", "soc_0-5cm_mean.tif", 10.0),
             ("nitrogen_gkg", "nitrogen_0-5cm_mean.tif", 100.0)]

# Bhuvan (ISRO/NRSC) geomorphology and lineament layers. Pulled once by
# scripts/fetch_cell_bhuvan.py and then stored, because these layers are static
# and a live third-party query has no place on the map refresh path.
BHUVAN_CSV = os.path.join(ROOT, "07_GEOLOGY", "Bhuvan", "cell_bhuvan_out.csv")
BHUVAN_NUM = ["geomorph_l1", "geomorph_l2", "lineament_dist_km",
              "lineament_n", "lineament_mag"]
BHUVAN_TEXT = ["geomorph_des", "lineament_des"]

EXCLUDE_ROAD = {"path", "footway", "steps", "cycleway", "bridleway", "pedestrian", "pedestrian"}
NER_BBOX = (87.0, 21.0, 98.0, 30.0)
AEQD = "+proj=aeqd +lat_0=25.5 +lon_0=92.5 +datum=WGS84 +units=m +no_defs"


def terrain_at(lons, lats):
    """elevation, slope, aspect, curvature, tri from Copernicus DEM GLO-30."""
    out = {k: np.full(len(lons), np.nan) for k in
           ("elevation_m", "slope_deg", "aspect_deg", "curvature_1pm", "tri_m")}
    tiles = np.array([""] * len(lons), dtype=object)
    dem_dir = os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "raw")

    for tp in sorted(glob.glob(os.path.join(dem_dir, "*.tif"))):
        with rasterio.open(tp) as src:
            b = src.bounds
            m = (lons >= b.left) & (lons < b.right) & (lats >= b.bottom) & (lats < b.top)
            idx = np.where(m)[0]
            if idx.size == 0:
                continue
            dem = src.read(1).astype(np.float32)
            h, w = dem.shape
            lats_row = src.transform.f + (np.arange(h) + 0.5) * src.transform.e
            px_m_lat, px_m_lon = stp.meters_per_degree(lats_row)
            px_m_lat = px_m_lat * abs(src.transform.e)
            px_m_lon = px_m_lon * src.transform.a
            slope, aspect, curv, tri = stp.derive(dem, src.transform, px_m_lat, px_m_lon)
            for i in idx:
                r, c = src.index(float(lons[i]), float(lats[i]))
                if not (0 <= r < h and 0 <= c < w):
                    continue
                out["elevation_m"][i] = dem[r, c]
                out["slope_deg"][i] = slope[r, c]
                out["aspect_deg"][i] = aspect[r, c]
                out["curvature_1pm"][i] = curv[r, c]
                out["tri_m"][i] = tri[r, c]
                tiles[i] = os.path.basename(tp)
    out["dem_tile"] = tiles
    return out


def landcover_at(lons, lats):
    """WorldCover class at the point plus class shares within ~500 m."""
    res = {"landcover_class": np.full(len(lons), np.nan),
           "landcover_name": np.array([""] * len(lons), dtype=object),
           "lc_tile": np.array([""] * len(lons), dtype=object)}
    for k in LC_PCT:
        res[k] = np.full(len(lons), np.nan)

    tile_dir = os.path.join(ROOT, "08_LANDCOVER", "ESA_WorldCover", "2021_v200", "raw")
    for tp in sorted(glob.glob(os.path.join(tile_dir, "*.tif"))):
        with rasterio.open(tp) as src:
            b = src.bounds
            m = (lons >= b.left) & (lons < b.right) & (lats >= b.bottom) & (lats < b.top)
            idx = np.where(m)[0]
            if idx.size == 0:
                continue
            H, W = src.height, src.width
            for i in idx:
                lon, lat = float(lons[i]), float(lats[i])
                row, col = src.index(lon, lat)
                row = min(max(row, 0), H - 1)
                col = min(max(col, 0), W - 1)
                m_px_y = 110540.0 * (-src.transform.e)
                rad = max(2, int(round(BUFFER_M / m_px_y)))
                r0, r1 = max(0, row - rad), min(H, row + rad + 1)
                c0, c1 = max(0, col - rad), min(W, col + rad + 1)
                if r1 <= r0 or c1 <= c0:
                    continue
                arr = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))
                cls = int(arr[row - r0, col - c0])
                res["landcover_class"][i] = cls
                res["landcover_name"][i] = LC_CLASSES.get(cls, "unknown")
                res["lc_tile"][i] = os.path.basename(tp)
                valid = arr[arr > 0]
                if valid.size:
                    vals, counts = np.unique(valid, return_counts=True)
                    share = dict(zip(vals.tolist(), (counts / valid.size * 100.0).tolist()))
                    for k in LC_PCT:
                        res[k][i] = round(share.get(LC_CODE[k], 0.0), 2)
    return res


def soil_at(lons, lats):
    res = {}
    soil_dir = os.path.join(ROOT, "06_SOIL", "SoilGrids", "raw")
    for col, fname, factor in SOIL_SPEC:
        p = os.path.join(soil_dir, fname)
        if not os.path.exists(p):
            res[col] = np.full(len(lons), np.nan)
            continue
        with rasterio.open(p) as src:
            arr = src.read(1).astype("float64")
            H, W = src.height, src.width
            ci = np.clip(((lons - src.transform.c) / src.transform.a).astype(int), 0, W - 1)
            ri = np.clip(((lats - src.transform.f) / src.transform.e).astype(int), 0, H - 1)
        vals = np.full(len(lons), np.nan)
        for i in range(len(lons)):
            r0, r1 = max(0, ri[i] - 1), min(H, ri[i] + 2)
            c0, c1 = max(0, ci[i] - 1), min(W, ci[i] + 2)
            v = arr[r0:r1, c0:c1]
            v = v[v != 0]
            if v.size:
                vals[i] = v.mean() / factor
        res[col] = np.round(vals, 3)
    return res


def rain_climatology_at(lons, lats):
    """35-year IMD climatology: annual, monsoon, max 1-day, max 5-day."""
    files = rfp.year_files()
    print("      IMD year files: %d" % len(files))
    annual_sum = mons_sum = m1_sum = m5_sum = n_years = None
    lon_g = lat_g = None
    for yr in sorted(files):
        a, mt, m1, m5, lon_g, lat_g, _ = rfp.summarise(files[yr])
        if annual_sum is None:
            annual_sum = np.where(np.isnan(a), 0.0, a)
            mons_sum = np.where(np.isnan(mt), 0.0, mt)
            m1_sum = np.where(np.isnan(m1), 0.0, m1)
            m5_sum = np.where(np.isnan(m5), 0.0, m5)
            n_years = (~np.isnan(a)).astype("float64")
        else:
            annual_sum += np.where(np.isnan(a), 0.0, a)
            mons_sum += np.where(np.isnan(mt), 0.0, mt)
            m1_sum += np.where(np.isnan(m1), 0.0, m1)
            m5_sum += np.where(np.isnan(m5), 0.0, m5)
            n_years += (~np.isnan(a)).astype("float64")

    nz = np.maximum(n_years, 1)
    clim = {k: np.where(n_years > 0, v / nz, np.nan) for k, v in
            (("rain_clim_annual_mm", annual_sum), ("rain_clim_monsoon_mm", mons_sum),
             ("rain_clim_max1d_mm", m1_sum), ("rain_clim_max5d_mm", m5_sum))}

    nlat, nlon = clim["rain_clim_annual_mm"].shape
    res = {k: np.full(len(lons), np.nan) for k in clim}
    for i in range(len(lons)):
        c = int(round((lons[i] - lon_g[0]) / (lon_g[1] - lon_g[0])))
        r = int(round((lats[i] - lat_g[0]) / (lat_g[1] - lat_g[0])))
        if not (0 <= r < nlat and 0 <= c < nlon):
            continue
        for k in clim:
            v = clim[k][r, c]
            if np.isfinite(v):
                res[k][i] = round(float(v), 2)
    return res


def distances_at(lons, lats):
    """Distance to nearest road / river / water body, plus the road class."""
    import geopandas as gpd
    import shapely
    from shapely import STRtree
    import pyogrio

    osm = os.path.join(ROOT, "09_INFRASTRUCTURE", "OSM", "extracted")
    pg = gpd.GeoDataFrame(
        {"lon": lons, "lat": lats},
        geometry=gpd.points_from_xy(lons, lats), crs="EPSG:4326").to_crs(AEQD)
    pts = pg.geometry.values
    res = {}

    roads = pyogrio.read_dataframe(os.path.join(osm, "gis_osm_roads_free_1.shp"),
                                   bbox=NER_BBOX, columns=["fclass"])
    roads = roads[~roads["fclass"].isin(EXCLUDE_ROAD)].to_crs(AEQD)
    rg = roads.geometry.values
    idx = STRtree(rg).nearest(pts)
    res["dist_road_m"] = np.round(shapely.distance(pts, rg[idx]), 1)
    res["road_fclass"] = roads["fclass"].values[idx]

    ww = pyogrio.read_dataframe(os.path.join(osm, "gis_osm_waterways_free_1.shp"),
                                bbox=NER_BBOX, columns=["fclass"]).to_crs(AEQD)
    wg = ww.geometry.values
    res["dist_river_m"] = np.round(shapely.distance(pts, wg[STRtree(wg).nearest(pts)]), 1)

    wa = pyogrio.read_dataframe(os.path.join(osm, "gis_osm_water_a_free_1.shp"),
                                bbox=NER_BBOX, columns=["fclass"]).to_crs(AEQD)
    ag = wa.geometry.values
    res["dist_water_m"] = np.round(shapely.distance(pts, ag[STRtree(ag).nearest(pts)]), 1)
    return res


def bhuvan_at(cell_ids):
    """Geomorphology and lineament values for each cell, from the stored pull.

    Lineaments are sparse: the search is 27 km wide and several cells have none
    in range at all. That is recorded as a blank value plus a miss flag rather
    than as a zero, because zero would read as "the lineament runs through the
    point" - the opposite of what was found. The training table treats the same
    gap the same way.
    """
    if not os.path.exists(BHUVAN_CSV):
        print("      %s not found - run scripts/fetch_cell_bhuvan.py" % BHUVAN_CSV)
        return {}

    stored = {}
    with open(BHUVAN_CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            stored[str(row.get("id", "")).strip()] = row

    out = {}
    for cid in cell_ids:
        row = stored.get(cid) or {}
        entry = {}
        for col in BHUVAN_NUM:
            value = (row.get(col) or "").strip()
            entry[col] = float(value) if value else None
        for col in BHUVAN_TEXT:
            value = (row.get(col) or "").strip()
            entry[col] = value or None
        out[cid] = entry
    return out


def main():
    lons = np.array([c["centroid_lon"] for c in CELLS], dtype="float64")
    lats = np.array([c["centroid_lat"] for c in CELLS], dtype="float64")
    print("cells: %d" % len(CELLS))

    print("[1/6] terrain ..."); t = time.time()
    terrain = terrain_at(lons, lats)
    print("      %.1fs" % (time.time() - t))

    print("[2/6] land cover ..."); t = time.time()
    landcover = landcover_at(lons, lats)
    print("      %.1fs" % (time.time() - t))

    print("[3/6] soil ..."); t = time.time()
    soil = soil_at(lons, lats)
    print("      %.1fs" % (time.time() - t))

    print("[4/6] rainfall climatology ..."); t = time.time()
    rain = rain_climatology_at(lons, lats)
    print("      %.1fs" % (time.time() - t))

    print("[5/6] distances ..."); t = time.time()
    dist = distances_at(lons, lats)
    print("      %.1fs" % (time.time() - t))

    print("[6/6] bhuvan geology ..."); t = time.time()
    bhuvan = bhuvan_at([c["location_id"] for c in CELLS])
    print("      %.1fs" % (time.time() - t))

    cells = {}
    for i, cell in enumerate(CELLS):
        aspect = terrain["aspect_deg"][i]
        feats = {
            "elevation_m": round(float(terrain["elevation_m"][i]), 2),
            "slope_deg": round(float(terrain["slope_deg"][i]), 3),
            "curvature_1pm": round(float(terrain["curvature_1pm"][i]), 8),
            "tri_m": round(float(terrain["tri_m"][i]), 3),
            "aspect_sin": round(float(np.sin(np.radians(aspect))), 6),
            "aspect_cos": round(float(np.cos(np.radians(aspect))), 6),
            "landcover_class": float(landcover["landcover_class"][i]),
        }
        for k in LC_PCT:
            feats[k] = float(landcover[k][i])
        for col, _, _ in SOIL_SPEC:
            feats[col] = float(soil[col][i])
        for k in rain:
            feats[k] = float(rain[k][i])
        for k in ("dist_road_m", "dist_river_m", "dist_water_m"):
            feats[k] = float(dist[k][i])

        bv = bhuvan.get(cell["location_id"], {})
        for col in BHUVAN_NUM + BHUVAN_TEXT:
            feats[col] = bv.get(col)

        feats["miss_rain_clim"] = 0.0 if np.isfinite(rain["rain_clim_annual_mm"][i]) else 1.0
        feats["miss_soil"] = 0.0 if np.isfinite(soil["clay_gkg"][i]) else 1.0
        feats["miss_geomorph"] = 0.0 if bv.get("geomorph_l1") is not None else 1.0
        feats["miss_lineament"] = 0.0 if bv.get("lineament_dist_km") is not None else 1.0

        cells[cell["location_id"]] = {
            "name": cell["name"],
            "district": cell["district"],
            "state": cell["state"],
            "centroid_lat": cell["centroid_lat"],
            "centroid_lon": cell["centroid_lon"],
            "static_features": feats,
            "road_fclass": str(dist["road_fclass"][i]),
            "provenance": {
                "dem_tile": str(terrain["dem_tile"][i]),
                "landcover_tile": str(landcover["lc_tile"][i]),
                "landcover_name": str(landcover["landcover_name"][i]),
                "soil_source": "SoilGrids 0-5cm mean",
                "rainfall_source": "IMD 0.25deg RF25 1991-2025 climatology",
                "distance_source": "OpenStreetMap India (Geofabrik)",
                "geology_source": ("Bhuvan (ISRO/NRSC) GSI geomorphology + "
                                   "lineament 1:50,000, stored by "
                                   "scripts/fetch_cell_bhuvan.py"),
            },
        }

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "generator": "scripts/extract_cell_features.py",
        "note": ("Static per-cell features for the 10 NER monitoring cells, "
                 "extracted with the same logic as the training points. "
                 "Live rainfall and soil moisture are not stored here - they "
                 "arrive from the live pipeline on every cycle."),
        "sources": source_signature(),
        "cells": cells,
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print("\nwrote %s" % OUT_JSON)
    print("\n%-8s %-22s %8s %7s %9s %8s %9s %8s" %
          ("cell", "name", "elev_m", "slope", "rain_mm", "clay", "road_m", "lc"))
    for cid, c in cells.items():
        f = c["static_features"]
        print("%-8s %-22s %8.0f %7.1f %9.0f %8.0f %9.0f %8.0f" %
              (cid, c["name"][:22], f["elevation_m"], f["slope_deg"],
               f["rain_clim_annual_mm"], f["clay_gkg"], f["dist_road_m"],
               f["landcover_class"]))


if __name__ == "__main__":
    main()