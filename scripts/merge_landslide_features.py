"""
Merge the five per-point extraction tables into one assembled feature table.

Inputs (all produced from the same point list, in the same row order)
  05_TERRAIN/.../terrain_at_points.csv
  04_RAINFALL/derived/rainfall_at_points.csv
  08_LANDCOVER/derived/landcover_at_points.csv
  06_SOIL/derived/soil_at_points.csv
  09_INFRASTRUCTURE/derived/distances_at_points.csv

Join key
  NOT SLIDE_NO. The inventory has 8,546 points but only 8,535 unique SLIDE_NO
  values, so an 11-way duplicate would fan out into a cartesian product.
  Rows are joined on position after verifying that the SLIDE_NO sequence is
  identical across every file - if any file is out of step the script aborts
  rather than producing a silently misaligned table.

This table is POSITIVES ONLY (every row is a recorded landslide). Negatives are
generated separately, so the file is named ..._positive.csv to keep that obvious.

Output
  13_MODEL_DATASETS/landslide_features_positive.csv
"""

import os
import sys
import numpy as np
import pandas as pd

ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
OUT_DIR = os.path.join(ROOT, "13_MODEL_DATASETS")

# "pos" assembles the positive (recorded landslide) table, "neg" the sampled
# negatives. Same five sources, same column order - only the filename suffix,
# the point_id prefix and the label value differ. Building both through one
# script is what guarantees the two tables are structurally identical.
TAG = (sys.argv[1] if len(sys.argv) > 1 else "pos").lower()
if TAG not in ("pos", "neg"):
    sys.exit("usage: merge_landslide_features.py [pos|neg]")
SUFFIX = "_at_points.csv" if TAG == "pos" else "_at_negative_points.csv"
LABEL = 1 if TAG == "pos" else 0
OUT_CSV = os.path.join(OUT_DIR, "landslide_features_%s.csv"
                       % ("positive" if TAG == "pos" else "negative"))

SRC = [
    ("terrain",   os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "derived", "terrain" + SUFFIX)),
    ("rainfall",  os.path.join(ROOT, "04_RAINFALL", "derived", "rainfall" + SUFFIX)),
    ("landcover", os.path.join(ROOT, "08_LANDCOVER", "derived", "landcover" + SUFFIX)),
    ("soil",      os.path.join(ROOT, "06_SOIL", "derived", "soil" + SUFFIX)),
    ("distance",  os.path.join(ROOT, "09_INFRASTRUCTURE", "derived", "distances" + SUFFIX)),
]

# columns to carry over from each source, beyond the join key
KEEP = {
    "terrain":   ["SLIDE_NO", "STATE", "DISTRICT", "INITIATION", "lon", "lat",
                  "elevation_m", "slope_deg", "aspect_deg", "curvature_1pm",
                  "tri_m", "dem_tile", "edge_pixel"],
    "rainfall":  ["SLIDE_NO", "event_year", "year_source",
                  "rain_clim_annual_mm", "rain_clim_monsoon_mm",
                  "rain_clim_max1d_mm", "rain_clim_max5d_mm",
                  "rain_annual_mm", "rain_monsoon_mm",
                  "rain_monsoon_max1d_mm", "rain_monsoon_max5d_mm",
                  "rain_anomaly", "rain_monsoon_anomaly", "rain_data_gap"],
    "landcover": ["SLIDE_NO", "landcover_class", "landcover_name",
                  "lc_tree_pct", "lc_shrub_pct", "lc_grass_pct", "lc_crop_pct",
                  "lc_built_pct", "lc_bare_pct", "lc_snow_pct", "lc_water_pct",
                  "lc_wetland_pct", "lc_mangrove_pct", "lc_moss_pct"],
    "soil":      ["SLIDE_NO", "clay_gkg", "sand_gkg", "silt_gkg",
                  "bulk_density_kgdm3", "soc_gkg", "nitrogen_gkg", "texture_sum_gkg"],
    "distance":  ["SLIDE_NO", "dist_road_m", "dist_road_km", "road_fclass",
                  "dist_river_m", "dist_river_km", "dist_water_m", "dist_water_km"],
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    frames = {}
    for name, path in SRC:
        if not os.path.exists(path):
            sys.exit("missing input: %s" % path)
        df = pd.read_csv(path)
        miss = [c for c in KEEP[name] if c not in df.columns]
        if miss:
            sys.exit("%s is missing columns %s" % (name, miss))
        frames[name] = df[KEEP[name]].copy()
        print("%-10s %5d rows  %3d cols" % (name, len(df), len(KEEP[name])))

    # ---- alignment guard ----
    n = len(frames["terrain"])
    base_ids = frames["terrain"]["SLIDE_NO"].astype(str).values
    for name, df in frames.items():
        if len(df) != n:
            sys.exit("ROW COUNT MISMATCH: terrain=%d %s=%d" % (n, name, len(df)))
        other = df["SLIDE_NO"].astype(str).values
        if not np.array_equal(base_ids, other):
            bad = int((base_ids != other).sum())
            sys.exit("ROW ORDER MISMATCH in %s: %d rows differ" % (name, bad))
    print("\nalignment check passed: all %d rows in step across 5 sources" % n)

    merged = frames["terrain"].copy()
    for name in ["rainfall", "landcover", "soil", "distance"]:
        add = frames[name].drop(columns=["SLIDE_NO"])
        merged = pd.concat([merged, add], axis=1)

    # point_id must be unique across BOTH tables, otherwise the stacked dataset
    # has colliding keys. Positives keep the pos_ prefix, negatives get neg_.
    merged.insert(0, "point_id",
                  ["%s_%05d" % (TAG, i) for i in range(len(merged))])

    # hillside sanity flag from the terrain audit; kept, not dropped, so the
    # decision stays visible rather than silently baked in
    merged["low_slope_review"] = (merged["slope_deg"] < 10).astype(int)

    merged["landslide"] = LABEL

    merged.to_csv(OUT_CSV, index=False)
    print("\nwrote %s" % OUT_CSV)
    print("shape: %d rows x %d cols" % merged.shape)

    print("\n--- columns by group ---")
    for name, cols in KEEP.items():
        extra = len([c for c in cols if c != "SLIDE_NO"])
        print("  %-10s %2d" % (name, extra))
    print("  derived    %2d  (point_id, low_slope_review, landslide)" % 3)

    print("\n--- missing values per column (only columns with gaps) ---")
    mv = merged.isna().sum()
    mv = mv[mv > 0].sort_values(ascending=False)
    if len(mv) == 0:
        print("  none")
    else:
        for c, v in mv.items():
            print("  %-26s %5d  (%.1f%%)" % (c, v, 100 * v / len(merged)))

    print("\n--- sanity: ranges of key features ---")
    checks = ["elevation_m", "slope_deg", "rain_clim_annual_mm", "clay_gkg",
              "lc_tree_pct", "dist_road_m", "dist_river_m"]
    for c in checks:
        s = merged[c].dropna()
        print("  %-22s min %10.2f   median %10.2f   max %10.2f"
              % (c, s.min(), s.median(), s.max()))


if __name__ == "__main__":
    main()