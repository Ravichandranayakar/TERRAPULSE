"""
Extract SoilGrids (ISRIC) soil properties at landslide point locations.

Source
  6 rasters, 250 m, EPSG:4326, bounds lon 87-98 / lat 21-30 - exactly our NER box.
  Values are stored as scaled INTEGERS. The scale factor differs per property,
  which is the classic SoilGrids trap; using one factor for all six silently
  produces nonsense.

    property   raw unit      factor   -> reported unit
    clay       g/kg            1      -> g/kg
    sand       g/kg            1      -> g/kg
    silt       g/kg            1      -> g/kg
    bdod       cg/cm3        100      -> kg/dm3  (= g/cm3)
    soc        dg/kg          10      -> g/kg
    nitrogen   cg/kg         100      -> g/kg

  The texture factor was determined empirically, not taken from documentation.
  Summing the RAW clay+sand+silt integers gives exactly 1000 for 100% of pixels
  (p05=999, p95=1001), which is the definition of g/kg for a texture triangle.
  Applying the documented factor of 10 would have produced 3% clay over NER and
  silently corrupted the model. The other three were confirmed by physical range:
  bdod/100 = 1.16 kg/dm3, nitrogen/100 = 3.63 g/kg, soc/10 = 41.2 g/kg.

  The script re-checks this every run: clay + sand + silt must total ~1000 g/kg.

Sampling
  Each raster is 18.3e6 pixels (~73 MB), small enough to load whole and sample
  all points at once, which is far faster than per-point window reads.
  A 3x3 pixel window (~750 m) is averaged per point to damp single-cell noise.
  Zero is treated as no-data: bulk density cannot be zero, and exactly-zero
  texture fractions over NER do not occur.

Output
  06_SOIL/derived/soil_at_points.csv
"""

import os
import sys
import numpy as np
import pandas as pd
import rasterio

ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
SOIL_DIR = os.path.join(ROOT, "06_SOIL", "SoilGrids", "raw")
IN_CSV = os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "derived", "terrain_at_points.csv")
OUT_DIR = os.path.join(ROOT, "06_SOIL", "derived")
OUT_CSV = os.path.join(OUT_DIR, "soil_at_points.csv")

SPEC = [
    ("clay",     "clay_0-5cm_mean.tif",     "clay_gkg",      1.0),
    ("sand",     "sand_0-5cm_mean.tif",     "sand_gkg",      1.0),
    ("silt",     "silt_0-5cm_mean.tif",     "silt_gkg",      1.0),
    ("bdod",     "bdod_0-5cm_mean.tif",     "bulk_density_kgdm3", 100.0),
    ("soc",      "soc_0-5cm_mean.tif",      "soc_gkg",      10.0),
    ("nitrogen", "nitrogen_0-5cm_mean.tif", "nitrogen_gkg", 100.0),
]

RAD = 1  # 3x3 window


def sample_raster(path, factor, lons, lats):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        H, W = src.height, src.width
        a = src.transform.a
        e = src.transform.e
        c0 = src.transform.c
        f0 = src.transform.f

    col = ((lons - c0) / a).astype(int)
    row = ((lats - f0) / e).astype(int)
    col = np.clip(col, 0, W - 1)
    row = np.clip(row, 0, H - 1)

    out = np.full(len(lons), np.nan)
    for i in range(len(lons)):
        r0 = max(0, row[i] - RAD); r1 = min(H, row[i] + RAD + 1)
        c0i = max(0, col[i] - RAD); c1 = min(W, col[i] + RAD + 1)
        w = arr[r0:r1, c0i:c1]
        v = w[w != 0]
        if v.size:
            out[i] = v.mean() / factor
    return out


def main():
    in_csv = sys.argv[1] if len(sys.argv) > 1 else IN_CSV
    out_csv = sys.argv[2] if len(sys.argv) > 2 else OUT_CSV
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)

    pts = pd.read_csv(in_csv)
    lons = pts["lon"].values.astype("float64")
    lats = pts["lat"].values.astype("float64")
    print("points: %d" % len(pts))

    df = pts[["SLIDE_NO", "STATE", "lon", "lat"]].copy()

    for label, fname, colname, factor in SPEC:
        p = os.path.join(SOIL_DIR, fname)
        if not os.path.exists(p):
            print("  MISSING %s" % fname)
            df[colname] = np.nan
            continue
        df[colname] = np.round(sample_raster(p, factor, lons, lats), 3)
        s = df[colname].dropna()
        print("  %-9s factor=%-6.0f  n=%d  mean=%.3f  min=%.3f  max=%.3f"
              % (label, factor, len(s), s.mean(), s.min(), s.max()))

    # scaling self-check: texture fractions must total ~1000 g/kg
    df["texture_sum_gkg"] = (df["clay_gkg"] + df["sand_gkg"] + df["silt_gkg"]).round(2)

    df.to_csv(out_csv, index=False)
    print("\nwrote %s" % out_csv)

    print("\n--- coverage ---")
    for _, _, colname, _ in SPEC:
        print("  %-20s present %d / %d" % (colname, df[colname].notna().sum(), len(df)))

    t = df["texture_sum_gkg"].dropna()
    print("\n--- SCALING CHECK: clay + sand + silt (should be ~1000 g/kg) ---")
    print("  n=%d  mean=%.1f  median=%.1f  p05=%.1f  p95=%.1f  min=%.1f  max=%.1f"
          % (len(t), t.mean(), t.median(), t.quantile(.05), t.quantile(.95), t.min(), t.max()))
    near = ((t >= 900) & (t <= 1100)).mean() * 100
    print("  within 900-1100 g/kg: %.1f%% of points" % near)

    print("\n--- summary ---")
    cols = ["clay_gkg", "sand_gkg", "silt_gkg", "bulk_density_kgdm3", "soc_gkg", "nitrogen_gkg"]
    print(df[cols].describe().round(2).to_string())


if __name__ == "__main__":
    main()