"""
Sample terrain derivatives from Copernicus DEM GLO-30 at point locations.

Computes, per point:
  elevation_m, slope_deg, aspect_deg, curvature_1pm, tri_m

Method
  Gradients use true ground spacing (metres), corrected for latitude, matching
  the approach used by gdaldem. Curvature is the map-plane Laplacian (1/m).
  TRI is Riley terrain ruggedness index over a 3x3 window.

Notes
  Copernicus DEM GLO-30 stores ocean as 0 (no nodata value). Points sampling to
  elevation <= 0 are flagged as water/void and reported, not silently kept.
  TWI is deliberately NOT computed here: it needs full-basin flow routing, and a
  local window would give misleading values.
"""
import os
import sys
import glob
import numpy as np
import pandas as pd
import rasterio

ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
DEM_DIR = os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "raw")
OUT_DIR = os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "derived")
OUT_CSV = os.path.join(OUT_DIR, "terrain_at_points.csv")
GSI = os.path.join(ROOT, "01_LANDSLIDE_LABELS", "GSI_Landslide_Inventory.shp", "GSI_Landslide_Inventory.geojson")

NER_STATES = {
    "assam", "arunachal pradesh", "manipur", "meghalaya",
    "mizoram", "nagaland", "sikkim", "tripura",
}

EDGE_PX = 2


def txt(v):
    if v is None:
        return ""
    return str(v).strip()


def meters_per_degree(lat_deg):
    lat = np.radians(lat_deg)
    m_lat = (111132.92 - 559.82 * np.cos(2 * lat) + 1.175 * np.cos(4 * lat)
             - 0.0023 * np.cos(6 * lat))
    m_lon = (111412.84 * np.cos(lat) - 93.5 * np.cos(3 * lat)
             + 0.118 * np.cos(5 * lat))
    return m_lat, m_lon


def derive(dem, transform, px_m_lat, px_m_lon):
    dz_drow, dz_dcol = np.gradient(dem)
    dz_dE = dz_dcol / px_m_lon[:, None]
    dz_dN = -dz_drow / px_m_lat[:, None]

    slope = np.degrees(np.arctan(np.hypot(dz_dE, dz_dN)))
    aspect = (np.degrees(np.arctan2(-dz_dE, -dz_dN)) + 360.0) % 360.0

    d2E = np.gradient(dz_dE, axis=1) / px_m_lon[:, None]
    d2N = -np.gradient(dz_dN, axis=0) / px_m_lat[:, None]
    curvature = d2E + d2N

    p = np.pad(dem, 1, mode="edge").astype(np.float64)
    c = p[1:-1, 1:-1]
    acc = np.zeros_like(c)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            acc += (p[1 + dr:1 + dr + dem.shape[0], 1 + dc:1 + dc + dem.shape[1]] - c) ** 2
    tri = np.sqrt(acc / 8.0)

    return slope, aspect, curvature, tri


def load_gsi_points():
    """GSI NER inventory -> point table (default behaviour)."""
    import json
    with open(GSI, encoding="utf-8") as fh:
        gj = json.load(fh)

    rows = []
    for feat in gj["features"]:
        pr = feat["properties"]
        st = txt(pr.get("STATE")).lower()
        if st not in NER_STATES:
            continue
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"][:2]
        rows.append({
            "SLIDE_NO": pr.get("SLIDE_NO"),
            "STATE": txt(pr.get("STATE")),
            "DISTRICT": txt(pr.get("DISTRICT")),
            "INITIATION": txt(pr.get("INITIATION")),
            "lon": float(lon),
            "lat": float(lat),
        })

    pts = pd.DataFrame(rows)
    print("GSI NER points loaded: %d" % len(pts))
    print(pts["STATE"].value_counts().to_string())
    print()
    return pts


def load_csv_points(path):
    """Arbitrary point table (lon/lat) -> same schema, e.g. negative samples."""
    df = pd.read_csv(path)
    low = {str(c).lower(): c for c in df.columns}
    lon_col = low.get("lon") or low.get("longitude") or low.get("x")
    lat_col = low.get("lat") or low.get("latitude") or low.get("y")
    if lon_col is None or lat_col is None:
        raise SystemExit("input CSV needs lon/lat columns, got: %s" % list(df.columns))
    # Keep the caller's identifier when the file carries one. Falling back to the
    # row index silently renumbers the points, and a later join on SLIDE_NO then
    # matches nothing - which is how every curated row lost its label.
    key_col = low.get("slide_no") or low.get("report_id") or low.get("neg_id")
    pts = pd.DataFrame({
        "SLIDE_NO": df[key_col] if key_col else pd.Series(range(len(df))),
        "STATE": df[low["state"]].astype(str) if "state" in low else "",
        "DISTRICT": df[low["district"]].astype(str) if "district" in low else "",
        "INITIATION": "",
        "lon": pd.to_numeric(df[lon_col], errors="coerce"),
        "lat": pd.to_numeric(df[lat_col], errors="coerce"),
    })
    print("CSV points loaded: %d" % len(pts))
    print("  lon %.4f .. %.4f   lat %.4f .. %.4f"
          % (pts["lon"].min(), pts["lon"].max(), pts["lat"].min(), pts["lat"].max()))
    print()
    return pts


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    in_csv = sys.argv[1] if len(sys.argv) > 1 else ""
    out_csv = sys.argv[2] if len(sys.argv) > 2 else OUT_CSV
    pts = load_csv_points(in_csv) if in_csv else load_gsi_points()

    tiles = sorted(glob.glob(os.path.join(DEM_DIR, "*.tif")))
    print("DEM tiles: %d" % len(tiles))

    out = np.full((len(pts), 5), np.nan, dtype=np.float64)
    src_tile = np.array([""] * len(pts), dtype=object)
    edge_flag = np.zeros(len(pts), dtype=np.int8)

    for ti, tp in enumerate(tiles, 1):
        with rasterio.open(tp) as src:
            b = src.bounds
            m = ((pts["lon"] >= b.left) & (pts["lon"] < b.right)
                 & (pts["lat"] >= b.bottom) & (pts["lat"] < b.top)).values
            idx = np.where(m)[0]
            if idx.size == 0:
                continue

            dem = src.read(1).astype(np.float32)
            h, w = dem.shape
            transform = src.transform
            lats = transform.f + (np.arange(h) + 0.5) * transform.e
            px_m_lat, px_m_lon = meters_per_degree(lats)
            px_m_lat = px_m_lat * abs(transform.e)
            px_m_lon = px_m_lon * transform.a

            slope, aspect, curv, tri = derive(dem, transform, px_m_lat, px_m_lon)

            for i in idx:
                lon = pts["lon"].iat[i]
                lat = pts["lat"].iat[i]
                r, c = src.index(lon, lat)
                if not (0 <= r < h and 0 <= c < w):
                    continue
                out[i] = (dem[r, c], slope[r, c], aspect[r, c], curv[r, c], tri[r, c])
                src_tile[i] = os.path.basename(tp)
                if r < EDGE_PX or r >= h - EDGE_PX or c < EDGE_PX or c >= w - EDGE_PX:
                    edge_flag[i] = 1

        if ti % 10 == 0 or ti == len(tiles):
            print("  [%d/%d] tiles processed, %d points filled"
                  % (ti, len(tiles), int(np.isfinite(out[:, 0]).sum())))

    res = pts.copy()
    res["elevation_m"] = out[:, 0]
    res["slope_deg"] = out[:, 1]
    res["aspect_deg"] = out[:, 2]
    res["curvature_1pm"] = out[:, 3]
    res["tri_m"] = out[:, 4]
    res["dem_tile"] = src_tile
    res["edge_pixel"] = edge_flag

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    res.to_csv(out_csv, index=False)
    print("\nWrote %s" % out_csv)

    got = res["elevation_m"].notna()
    print("\n--- coverage ---")
    print("points total        : %d" % len(res))
    print("elevation sampled   : %d" % int(got.sum()))
    print("no DEM tile matched : %d" % int((~got).sum()))
    valid = got & (res["elevation_m"] > 0)
    print("valid land (elev>0) : %d" % int(valid.sum()))
    print("water/void (elev<=0): %d" % int((got & (res["elevation_m"] <= 0)).sum()))
    print("edge pixels (flag)  : %d" % int(res["edge_pixel"].sum()))

    print("\n--- terrain stats (valid land) ---")
    print(res.loc[valid, ["elevation_m", "slope_deg", "aspect_deg", "curvature_1pm", "tri_m"]]
          .describe().round(5).to_string())


if __name__ == "__main__":
    main()