"""
Generate negative (non-landslide) sample points for the NER landslide model.

Why this file exists
  No dataset anywhere contains confirmed non-landslide locations. Inventories are
  presence-only: GSI records where landslides happened, never where they did not.
  Absences are therefore constructed here, and the construction method is a
  modelling decision that has to be documented.

Method
  1. Candidate pool
     Uniform random points inside the union of the 8 NER state polygons
     (GADM 4.1 level 1). Not a bounding box - a box would scatter points into
     Bangladesh and the Brahmaputra plain where the inventory has no coverage.
  2. Exclusion
     Drop any candidate within 500 m of a recorded landslide. Otherwise a point
     could sit on an unrecorded slide and be mislabelled as a negative.
  3. Terrain + road scoring
     Slope and elevation from Copernicus DEM GLO-30, distance to the nearest
     motorable OSM road. Computed for every candidate.
  4. Stratified matching
     Positives are binned on (slope x elevation x distance-to-road). Each bin
     contributes the same number of negatives as it has positives.
     Two reasons this matters:
       - without terrain matching the model only learns "steep = landslide"
       - 67% of positives lie within 200 m of a road, because field teams reach
         slides by road. Random negatives would make distance-to-road a trivial
         separator that measures survey accessibility, not hazard.

Output
  13_MODEL_DATASETS/negative_points.csv   (plus a diagnostics printout)
"""

import os
import sys
import glob
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely import STRtree
import rasterio
import pyogrio

ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
BOUND = os.path.join(ROOT, "09_INFRASTRUCTURE", "boundaries", "gadm41_IND_1.json")
DEM = os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "raw")
OSM = os.path.join(ROOT, "09_INFRASTRUCTURE", "OSM", "extracted")
POS = os.path.join(ROOT, "13_MODEL_DATASETS", "landslide_features_positive.csv")
OUT_DIR = os.path.join(ROOT, "13_MODEL_DATASETS")
OUT_CSV = os.path.join(OUT_DIR, "negative_points.csv")
OUT_CAND = os.path.join(OUT_DIR, "_negative_candidates_scored.csv")

NER_STATES = ["Assam", "ArunachalPradesh", "Manipur", "Meghalaya",
              "Mizoram", "Nagaland", "Sikkim", "Tripura"]
EXCLUDE_ROAD = {"path", "footway", "steps", "cycleway", "bridleway", "pedestrian"}
AEQD = "+proj=aeqd +lat_0=25.5 +lon_0=92.5 +datum=WGS84 +units=m +no_defs"

N_TARGET = int(os.environ.get("N_TARGET", "8546"))
N_CAND = int(os.environ.get("N_CAND", "300000"))
SEED = 42
NB_SLOPE = 5
NB_ELEV = 4
NB_ROAD = 5


def meters_per_degree(lat_deg):
    lat = np.radians(lat_deg)
    m_lat = (111132.92 - 559.82 * np.cos(2 * lat) + 1.175 * np.cos(4 * lat)
             - 0.0023 * np.cos(6 * lat))
    m_lon = (111412.84 * np.cos(lat) - 93.5 * np.cos(3 * lat)
             + 0.118 * np.cos(5 * lat))
    return m_lat, m_lon


def terrain_at(points, label):
    """slope/elevation for arbitrary points, reading each DEM tile once."""
    lon = points["lon"].values
    lat = points["lat"].values
    elev = np.full(len(points), np.nan)
    slope = np.full(len(points), np.nan)

    for tp in sorted(glob.glob(os.path.join(DEM, "*.tif"))):
        with rasterio.open(tp) as src:
            b = src.bounds
            m = (lon >= b.left) & (lon < b.right) & (lat >= b.bottom) & (lat < b.top)
            idx = np.where(m)[0]
            if idx.size == 0:
                continue
            dem = src.read(1).astype(np.float32)
            H, W = dem.shape
            tr = src.transform
            lats = tr.f + (np.arange(H) + 0.5) * tr.e
            mpd_lat, mpd_lon = meters_per_degree(lats)
            px_lat = mpd_lat * abs(tr.e)
            px_lon = mpd_lon * tr.a

            dz_drow, dz_dcol = np.gradient(dem)
            dz_dE = dz_dcol / px_lon[:, None]
            dz_dN = -dz_drow / px_lat[:, None]
            sl = np.degrees(np.arctan(np.hypot(dz_dE, dz_dN)))

            for i in idx:
                r, c = src.index(lon[i], lat[i])
                r = min(max(r, 0), H - 1); c = min(max(c, 0), W - 1)
                elev[i] = dem[r, c]
                slope[i] = sl[r, c]
    print("    %-12s scored in terrain pass (%d/%d)" % (label, np.isfinite(elev).sum(), len(points)))
    return elev, slope


def road_distance(points):
    pg = gpd.GeoDataFrame(geometry=gpd.points_from_xy(points["lon"], points["lat"]),
                          crs="EPSG:4326").to_crs(AEQD)
    roads = pyogrio.read_dataframe(os.path.join(OSM, "gis_osm_roads_free_1.shp"),
                                   bbox=(87, 21, 98, 30), columns=["fclass"])
    roads = roads[~roads["fclass"].isin(EXCLUDE_ROAD)].to_crs(AEQD)
    rg = roads.geometry.values
    tree = STRtree(rg)
    idx = tree.nearest(pg.geometry.values)
    d = shapely.distance(pg.geometry.values, rg[idx])
    return d


def main():
    rng = np.random.default_rng(SEED)
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---------- study area ----------
    g = gpd.read_file(BOUND)
    norm = g["NAME_1"].astype(str).str.replace(" ", "", regex=False)
    sel = g[norm.isin(NER_STATES)].copy()
    print("NER state polygons found: %d of 8  (%s)"
          % (len(sel), ", ".join(sorted(sel["NAME_1"].unique()))))
    if len(sel) == 0:
        sys.exit("no NER boundaries matched")
    area = sel.geometry.union_all()
    minx, miny, maxx, maxy = area.bounds
    print("study area bounds: lon %.2f..%.2f lat %.2f..%.2f" % (minx, maxx, miny, maxy))

    # ---------- positives ----------
    pos = pd.read_csv(POS)
    print("positives: %d" % len(pos))

    # ---------- candidate pool ----------
    # Uniform sampling alone cannot populate the (steep AND near-road) corner of
    # the covariate space where 67% of the positives live, which made matching
    # fail: the first attempt produced negatives a median 732 m from a road
    # against 30 m for positives. Half the pool is therefore drawn along the road
    # network with a random offset, so the strata that matter actually exist.
    print("\ngenerating candidates (uniform + near-road mix)...")

    n_uniform = N_CAND // 2
    n_roadside = N_CAND - n_uniform

    cx = rng.uniform(minx, maxx, n_uniform)
    cy = rng.uniform(miny, maxy, n_uniform)
    uni_pts = shapely.points(cx, cy)
    uni_keep = shapely.contains(area, uni_pts)
    cand_u = pd.DataFrame({"lon": cx[uni_keep], "lat": cy[uni_keep]})
    print("  uniform inside NER      : %d" % len(cand_u))

    roads_for_gen = pyogrio.read_dataframe(
        os.path.join(OSM, "gis_osm_roads_free_1.shp"),
        bbox=(87, 21, 98, 30), columns=["fclass"])
    roads_for_gen = roads_for_gen[~roads_for_gen["fclass"].isin(EXCLUDE_ROAD)]
    rg_aeqd = roads_for_gen.to_crs(AEQD).geometry.values
    seg_len = shapely.length(rg_aeqd)
    seg_len = np.where(np.isfinite(seg_len) & (seg_len > 0), seg_len, 0.0)
    cum = np.cumsum(seg_len)
    total_len = cum[-1]
    print("  road network length     : %.0f km" % (total_len / 1000))

    d = rng.uniform(0.0, total_len, n_roadside)
    seg_i = np.searchsorted(cum, d)
    seg_i = np.clip(seg_i, 0, len(rg_aeqd) - 1)
    prev = np.concatenate([[0.0], cum[:-1]])
    local = d - prev[seg_i]
    base = shapely.line_interpolate_point(rg_aeqd[seg_i], local)
    bx = shapely.get_x(base)
    by = shapely.get_y(base)
    ang = rng.uniform(0, 2 * np.pi, n_roadside)
    rad = rng.uniform(0, 500.0, n_roadside)
    ox = bx + np.cos(ang) * rad
    oy = by + np.sin(ang) * rad
    road_pts = gpd.GeoSeries(shapely.points(ox, oy), crs=AEQD).to_crs("EPSG:4326")
    rl = np.array([g.x for g in road_pts])
    rt = np.array([g.y for g in road_pts])
    cand_r = pd.DataFrame({"lon": rl, "lat": rt})
    cand_r = cand_r.dropna()
    print("  roadside (within 500 m) : %d" % len(cand_r))
    del roads_for_gen, rg_aeqd

    cand = (pd.concat([cand_u, cand_r], ignore_index=True)
              .dropna().drop_duplicates().reset_index(drop=True))

    # The roadside pool is drawn along roads inside a lat/lon box, and that box
    # also covers West Bengal, Bihar and Jharkhand. Without this filter the
    # negatives escape the study area - 1,547 did in the first run, the furthest
    # 478 km away - which would teach the model "outside NER = no landslide".
    in_area = shapely.contains(
        area, shapely.points(cand["lon"].values, cand["lat"].values))
    dropped = int((~in_area).sum())
    cand = cand[in_area].reset_index(drop=True)
    print("  candidate pool total    : %d   (%d dropped outside the NER polygons)"
          % (len(cand), dropped))

    # ---------- exclusion zone ----------
    pos_g = gpd.GeoDataFrame(geometry=gpd.points_from_xy(pos["lon"], pos["lat"]),
                             crs="EPSG:4326").to_crs(AEQD)
    cand_g = gpd.GeoDataFrame(geometry=gpd.points_from_xy(cand["lon"], cand["lat"]),
                              crs="EPSG:4326").to_crs(AEQD)
    tree = STRtree(pos_g.geometry.values)
    near = tree.query(cand_g.geometry.values, predicate="dwithin", distance=500.0)
    excluded = set(near[1].tolist()) if len(near) else set()
    cand["near_landslide"] = 0
    if excluded:
        cand.loc[list(excluded), "near_landslide"] = 1
    before = len(cand)
    cand = cand[cand["near_landslide"] == 0].reset_index(drop=True)
    print("  excluded within 500 m of a landslide: %d  ->  %d remain"
          % (before - len(cand), len(cand)))

    # ---------- scoring ----------
    print("\nscoring candidates...")
    elev, slope = terrain_at(cand, "candidates")
    cand["elevation_m"] = elev
    cand["slope_deg"] = slope
    cand = cand[np.isfinite(cand["slope_deg"]) & (cand["elevation_m"] > 0)].reset_index(drop=True)
    print("  after dropping ocean/void: %d" % len(cand))

    cand["dist_road_m"] = road_distance(cand)
    print("  road distance computed")

    # reuse already-extracted positive features
    p = pos[["SLIDE_NO", "lon", "lat", "elevation_m", "slope_deg", "dist_road_m"]].dropna().copy()

    # ---------- stratified matching ----------
    sl_bins = np.quantile(p["slope_deg"], np.linspace(0, 1, NB_SLOPE + 1))
    el_bins = np.quantile(p["elevation_m"], np.linspace(0, 1, NB_ELEV + 1))
    rd_bins = np.quantile(p["dist_road_m"], np.linspace(0, 1, NB_ROAD + 1))
    for b in (sl_bins, el_bins, rd_bins):
        b[0], b[-1] = -np.inf, np.inf

    def key(df):
        return list(zip(np.digitize(df["slope_deg"], sl_bins),
                        np.digitize(df["elevation_m"], el_bins),
                        np.digitize(df["dist_road_m"], rd_bins)))

    p["_k"] = key(p)
    cand["_k"] = key(cand)

    pcount = p["_k"].value_counts()
    print("\nstrata: %d occupied by positives" % len(pcount))

    chosen = []
    shortfall = 0
    for k, want in pcount.items():
        pool = cand[cand["_k"] == k]
        if len(pool) == 0:
            shortfall += want
            continue
        take = min(want, len(pool))
        shortfall += want - take
        chosen.append(pool.sample(n=take, random_state=SEED))
    neg = pd.concat(chosen, ignore_index=True).head(N_TARGET) if chosen else pd.DataFrame()
    print("matched negatives: %d  (shortfall %d)" % (len(neg), shortfall))

    if len(neg) < N_TARGET:
        extra = cand.loc[~cand.index.isin(neg.index)] if len(neg) else cand
        need = N_TARGET - len(neg)
        print("  WARNING: strata shortfall of %d" % need)
        if len(extra) >= need:
            print("  topping up %d from nearest-remaining candidates" % need)
            neg = pd.concat([neg, extra.sample(n=need, random_state=SEED)],
                            ignore_index=True)

    neg = neg.reset_index(drop=True)
    neg.insert(0, "NEG_ID", ["NEG%05d" % i for i in range(len(neg))])
    # Give the negatives a state. STATE is not a feature - it is the grouping key
    # for spatial block CV, and a key that exists for one class only would make
    # blocked CV impossible. GADM spells "ArunachalPradesh" without the space,
    # the GSI inventory spells it with one, so normalise to the GSI form.
    ng = gpd.GeoDataFrame(geometry=gpd.points_from_xy(neg["lon"], neg["lat"]),
                          crs="EPSG:4326").to_crs(AEQD)
    j = gpd.sjoin(ng, sel[["NAME_1", "geometry"]].to_crs(AEQD),
                  how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    neg["STATE"] = (j["NAME_1"].reindex(neg.index).fillna("")
                    .str.replace("ArunachalPradesh", "Arunachal Pradesh",
                                 regex=False).values)
    print("\nnegatives per state:")
    print(neg["STATE"].replace("", "(unmatched)").value_counts().to_string())
    neg = neg[["NEG_ID", "lon", "lat", "STATE", "elevation_m", "slope_deg", "dist_road_m"]]
    neg.to_csv(OUT_CSV, index=False)
    cand.to_csv(OUT_CAND, index=False)
    print("\nwrote %s  (%d negatives)" % (OUT_CSV, len(neg)))

    # ---------- balance check ----------
    print("\n--- distribution match (positives vs negatives) ---")
    print("%-18s %10s %10s" % ("", "positives", "negatives"))
    for c in ["elevation_m", "slope_deg", "dist_road_m"]:
        print("%-18s %10.2f %10.2f   (median)" % (c, p[c].median(), neg[c].median()))
        print("%-18s %10.2f %10.2f   (mean)" % ("", p[c].mean(), neg[c].mean()))
        print("%-18s %10.2f %10.2f   (std)" % ("", p[c].std(), neg[c].std()))

    print("\n--- share within 200 m of a road ---")
    print("  positives: %.1f%%" % (100 * (p.dist_road_m < 200).mean()))
    print("  negatives: %.1f%%" % (100 * (neg.dist_road_m < 200).mean()))


if __name__ == "__main__":
    main()