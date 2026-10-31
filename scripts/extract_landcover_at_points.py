"""
Extract ESA WorldCover 2021 v200 land cover at landslide point locations.

Source
  12 tiles, ESA_WorldCover_10m_2021_v200_{N21|N24|N27}{E087|E090|E093|E096}_Map.tif
  Each is 36000 x 36000 px covering 3 x 3 degrees, EPSG:4326, uint8.
  Class value 0 is nodata; the 11 real classes are 10..100.

Approach
  Each tile is ~1.3e9 pixels, so tiles are never loaded whole. For every point we
  read a small window centred on it:
      class value at the point
      share of each class within a ~500 m radius
  The radius in pixels is derived from latitude rather than hardcoded, because a
  degree of longitude shrinks with latitude.

Why the buffer matters
  A single pixel says almost nothing - one 10 m square could be a bare patch in a
  forest. The surrounding mix describes the slope the point sits on, which is what
  the model actually needs. pct_bare and pct_built are also our proxy for
  unplanned hill cutting, which the problem statement names as a cause.

Output
  08_LANDCOVER/derived/landcover_at_points.csv
"""

import os
import sys
import glob
import math
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
TILE_DIR = os.path.join(ROOT, "08_LANDCOVER", "ESA_WorldCover", "2021_v200", "raw")
IN_CSV = os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "derived", "terrain_at_points.csv")
OUT_DIR = os.path.join(ROOT, "08_LANDCOVER", "derived")
OUT_CSV = os.path.join(OUT_DIR, "landcover_at_points.csv")

BUFFER_M = 500.0

CLASSES = {
    10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built",
    60: "bare", 70: "snow", 80: "water", 90: "wetland", 95: "mangrove",
    100: "moss",
}
PCT_COLS = ["lc_tree_pct", "lc_shrub_pct", "lc_grass_pct", "lc_crop_pct",
            "lc_built_pct", "lc_bare_pct", "lc_snow_pct", "lc_water_pct",
            "lc_wetland_pct", "lc_mangrove_pct", "lc_moss_pct"]
NAME_BY_PCT = dict(zip(PCT_COLS, CLASSES.keys()))


def main():
    in_csv = sys.argv[1] if len(sys.argv) > 1 else IN_CSV
    out_csv = sys.argv[2] if len(sys.argv) > 2 else OUT_CSV
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)

    pts = pd.read_csv(in_csv)
    print("points: %d" % len(pts))

    tiles = sorted(glob.glob(os.path.join(TILE_DIR, "*.tif")))
    print("worldcover tiles: %d" % len(tiles))

    out = np.full((len(pts), len(PCT_COLS) + 3), np.nan, dtype="float64")
    lc_class = np.full(len(pts), np.nan)
    lc_name = np.array([""] * len(pts), dtype=object)
    src_tile = np.array([""] * len(pts), dtype=object)

    lons = pts["lon"].values
    lats = pts["lat"].values

    for tp in tiles:
        with rasterio.open(tp) as src:
            b = src.bounds
            m = (lons >= b.left) & (lons < b.right) & (lats >= b.bottom) & (lats < b.top)
            idx = np.where(m)[0]
            if idx.size == 0:
                continue
            print("  %s : %d points" % (os.path.basename(tp), idx.size))

            # pixel size in degrees, then metres per pixel in each direction
            px_deg_x = src.transform.a
            px_deg_y = -src.transform.e
            H, W = src.height, src.width

            for i in idx:
                lon, lat = lons[i], lats[i]
                row, col = src.index(lon, lat)
                # A point sitting exactly on a tile boundary (measured: 12 Manipur
                # points at lat 24.0000, the N21/N24 seam) maps to row == H, one
                # past the last row. Clamp by one pixel instead of dropping it.
                row = min(max(row, 0), H - 1)
                col = min(max(col, 0), W - 1)

                m_per_px_y = 110540.0 * px_deg_y
                m_per_px_x = 111320.0 * math.cos(math.radians(lat)) * px_deg_x
                rad = max(2, int(round(BUFFER_M / m_per_px_y)))

                r0 = max(0, row - rad); r1 = min(H, row + rad + 1)
                c0 = max(0, col - rad); c1 = min(W, col + rad + 1)
                if r1 <= r0 or c1 <= c0:
                    continue

                win = Window(c0, r0, c1 - c0, r1 - r0)
                arr = src.read(1, window=win)

                lc_class[i] = arr[row - r0, col - c0]
                lc_name[i] = CLASSES.get(int(lc_class[i]), "unknown")
                src_tile[i] = os.path.basename(tp)

                valid = arr[arr > 0]
                n = valid.size
                out[i, 0] = n
                out[i, 1] = m_per_px_x
                out[i, 2] = m_per_px_y
                if n:
                    vals, counts = np.unique(valid, return_counts=True)
                    share = dict(zip(vals.tolist(), (counts / n * 100.0).tolist()))
                    for j, cn in enumerate(PCT_COLS):
                        out[i, 3 + j] = round(share.get(NAME_BY_PCT[cn], 0.0), 2)
                out[i, 2] = round(out[i, 2], 3)

    df = pts[["SLIDE_NO", "STATE", "lon", "lat"]].copy()
    df["landcover_class"] = lc_class
    df["landcover_name"] = lc_name
    df["lc_window_px"] = out[:, 0]
    df["lc_px_m_x"] = out[:, 1]
    df["lc_px_m_y"] = out[:, 2]
    for j, cn in enumerate(PCT_COLS):
        df[cn] = out[:, 3 + j]
    df["lc_tile"] = src_tile

    df.to_csv(out_csv, index=False)
    print("\nwrote %s" % out_csv)

    got = df["landcover_class"].notna() & (df["landcover_class"] > 0)
    print("\n--- coverage ---")
    print("points total      : %d" % len(df))
    print("class sampled     : %d" % int(got.sum()))
    print("nodata (class 0)  : %d" % int((df["landcover_class"] == 0).sum()))
    print("no tile matched   : %d" % int(df["landcover_class"].isna().sum()))

    print("\n--- class at the landslide point ---")
    vc = df.loc[got, "landcover_name"].value_counts()
    for k, v in vc.items():
        print("  %-10s %5d  (%.1f%%)" % (k, v, 100 * v / got.sum()))

    print("\n--- buffer composition, mean %% across points (valid windows) ---")
    for cn in PCT_COLS:
        s = df[cn].dropna()
        if len(s):
            print("  %-16s mean %6.2f%%   max %6.2f%%" % (cn, s.mean(), s.max()))

    print("\n--- buffered window check ---")
    print("median window px  : %.0f" % df.lc_window_px.median())
    print("median m/px x / y : %.2f / %.2f" % (df.lc_px_m_x.median(), df.lc_px_m_y.median()))


if __name__ == "__main__":
    main()