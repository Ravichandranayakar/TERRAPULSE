"""
Extract distance to nearest road, river and water body at point locations,
using OpenStreetMap India (Geofabrik extract).

Source
  gis_osm_roads_free_1.shp      4,333,599 lines India-wide, 242,180 inside NER
  gis_osm_waterways_free_1.shp    139,624 lines (rivers, streams, canals)
  gis_osm_water_a_free_1.shp      190,763 polygons (lakes, reservoirs)
  EPSG:4326. Read with a bbox filter so only NER features are loaded.

Distance method
  Straight-line distance in EPSG:4326 would be measured in DEGREES, which is
  meaningless as a model feature and is not a constant factor - a degree of
  longitude shrinks with latitude. Both the lines and the points are therefore
  projected to a local Azimuthal Equidistant CRS centred on NER
  (lat_0=25.5, lon_0=92.5), where distances are true metres.
  A Shapely STRtree gives the nearest geometry per point, then distance is
  measured against that geometry exactly - not against line vertices, which
  would overestimate.

Why these features
  Distance to road is the direct proxy for unplanned hill cutting, which the
  problem statement names as a cause: cut slopes beside roads destabilise.
  Footpaths and steps are excluded - they are not cut roads.
  Distance to river captures the toe-erosion and drainage-concentration effect.

Output
  09_INFRASTRUCTURE/derived/distances_at_points.csv
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely import STRtree
import pyogrio

ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
OSM = os.path.join(ROOT, "09_INFRASTRUCTURE", "OSM", "extracted")
OUT_DIR = os.path.join(ROOT, "09_INFRASTRUCTURE", "derived")
OUT_CSV = os.path.join(OUT_DIR, "distances_at_points.csv")
DEF_PTS = os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "derived", "terrain_at_points.csv")

NER_BBOX = (87.0, 21.0, 98.0, 30.0)
AEQD = "+proj=aeqd +lat_0=25.5 +lon_0=92.5 +datum=WGS84 +units=m +no_defs"

# not roads for our purpose - footpaths and steps are not cut hill roads
EXCLUDE_ROAD = {"path", "footway", "steps", "cycleway", "bridleway", "pedestrian"}


def nearest_km(tree, geoms, pts, label):
    t = time.time()
    idx = tree.nearest(pts)
    d = shapely.distance(pts, geoms[idx])
    print("    %-10s nearest resolved in %.1fs" % (label, time.time() - t))
    return idx, d


def main():
    pts_path = sys.argv[1] if len(sys.argv) > 1 else DEF_PTS
    out_path = sys.argv[2] if len(sys.argv) > 2 else OUT_CSV
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    pts = pd.read_csv(pts_path)
    print("points: %d  (%s)" % (len(pts), os.path.basename(pts_path)))

    pg = gpd.GeoDataFrame(
        pts[["SLIDE_NO", "STATE", "lon", "lat"]].copy(),
        geometry=gpd.points_from_xy(pts["lon"], pts["lat"]),
        crs="EPSG:4326",
    ).to_crs(AEQD)
    print("points projected to AEQD")

    out = {"dist_road_m": np.full(len(pts), np.nan),
           "dist_river_m": np.full(len(pts), np.nan),
           "dist_water_m": np.full(len(pts), np.nan)}
    road_class = np.array([""] * len(pts), dtype=object)

    # ---------------- roads ----------------
    t = time.time()
    roads = pyogrio.read_dataframe(os.path.join(OSM, "gis_osm_roads_free_1.shp"),
                                   bbox=NER_BBOX, columns=["fclass"])
    print("roads in NER: %d  (%.1fs)" % (len(roads), time.time() - t))
    roads = roads[~roads["fclass"].isin(EXCLUDE_ROAD)].copy()
    print("roads after excluding footpaths/steps: %d" % len(roads))
    roads = roads.to_crs(AEQD)
    rg = roads.geometry.values
    rt = STRtree(rg)
    idx, d = nearest_km(rt, rg, pg.geometry.values, "roads")
    out["dist_road_m"] = d
    fcls = roads["fclass"].values
    for i in range(len(pts)):
        road_class[i] = fcls[idx[i]]
    del roads, rg, rt

    # ---------------- rivers (waterway lines) ----------------
    t = time.time()
    ww = pyogrio.read_dataframe(os.path.join(OSM, "gis_osm_waterways_free_1.shp"),
                                bbox=NER_BBOX, columns=["fclass"])
    print("waterways in NER: %d  (%.1fs)" % (len(ww), time.time() - t))
    ww = ww.to_crs(AEQD)
    wg = ww.geometry.values
    wt = STRtree(wg)
    _, d = nearest_km(wt, wg, pg.geometry.values, "rivers")
    out["dist_river_m"] = d
    del ww, wg, wt

    # ---------------- water polygons ----------------
    t = time.time()
    wa = pyogrio.read_dataframe(os.path.join(OSM, "gis_osm_water_a_free_1.shp"),
                                bbox=NER_BBOX, columns=["fclass"])
    print("water bodies in NER: %d  (%.1fs)" % (len(wa), time.time() - t))
    wa = wa.to_crs(AEQD)
    ag = wa.geometry.values
    at = STRtree(ag)
    _, d = nearest_km(at, ag, pg.geometry.values, "water")
    out["dist_water_m"] = d
    del wa, ag, at

    df = pts[["SLIDE_NO", "STATE", "lon", "lat"]].copy()
    df["dist_road_m"] = np.round(out["dist_road_m"], 1)
    df["dist_road_km"] = np.round(out["dist_road_m"] / 1000.0, 4)
    df["road_fclass"] = road_class
    df["dist_river_m"] = np.round(out["dist_river_m"], 1)
    df["dist_river_km"] = np.round(out["dist_river_m"] / 1000.0, 4)
    df["dist_water_m"] = np.round(out["dist_water_m"], 1)
    df["dist_water_km"] = np.round(out["dist_water_m"] / 1000.0, 4)

    df.to_csv(out_path, index=False)
    print("\nwrote %s" % out_path)

    print("\n--- coverage ---")
    for c in ["dist_road_m", "dist_river_m", "dist_water_m"]:
        print("  %-14s present %d / %d" % (c, df[c].notna().sum(), len(df)))

    print("\n--- distance summary (km) ---")
    print(df[["dist_road_km", "dist_river_km", "dist_water_km"]]
          .describe(percentiles=[.05, .25, .5, .75, .95]).round(3).to_string())

    print("\n--- nearest road class ---")
    print(df["road_fclass"].value_counts().head(12).to_string())

    print("\n--- points very close to a road (<200 m) ---")
    print("  count: %d (%.1f%%)"
          % ((df.dist_road_m < 200).sum(), 100 * (df.dist_road_m < 200).mean()))
    print("--- points very close to a river (<200 m) ---")
    print("  count: %d (%.1f%%)"
          % ((df.dist_river_m < 200).sum(), 100 * (df.dist_river_m < 200).mean()))


if __name__ == "__main__":
    main()