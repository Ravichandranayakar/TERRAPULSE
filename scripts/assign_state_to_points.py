"""
Fill the STATE column for a points file using the GADM 4.1 level-1 boundaries.

Why
  The positive table carries STATE from the GSI inventory. The generated
  negatives were sampled from the union of the NER state polygons, so they have
  no state attached. STATE is not a model feature - it is the grouping key for
  spatial block cross-validation and for reporting where the negatives landed.
  A grouping key that exists for one class only would make blocked CV
  impossible, so it is filled here for the negatives.

Output
  rewrites the STATE column of the points CSV in place, and also writes a
  Bhuvan-ready points file (SLIDE_NO, STATE, lon, lat) beside the script.

Usage
  python assign_state_to_points.py <points.csv> [--id-col X] [--out-bhuvan Y]
"""

import argparse
import io
import os
import sys
import pandas as pd
import geopandas as gpd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
BOUND = os.path.join(ROOT, "09_INFRASTRUCTURE", "boundaries", "gadm41_IND_1.json")

NER_STATES = ["Assam", "ArunachalPradesh", "Manipur", "Meghalaya",
              "Mizoram", "Nagaland", "Sikkim", "Tripura"]
AEQD = "+proj=aeqd +lat_0=25.5 +lon_0=92.5 +datum=WGS84 +units=m +no_defs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("points")
    ap.add_argument("--id-col", default="")
    ap.add_argument("--out-bhuvan", default="")
    args = ap.parse_args()

    df = pd.read_csv(args.points)
    low = {str(c).lower(): c for c in df.columns}
    lon_col = low.get("lon") or low.get("longitude")
    lat_col = low.get("lat") or low.get("latitude")
    if lon_col is None or lat_col is None:
        sys.exit("need lon/lat columns, got %s" % list(df.columns))

    id_col = args.id_col or low.get("slide_no") or low.get("neg_id") or low.get("id")
    if id_col is None:
        df["_fid"] = range(len(df))
        id_col = "_fid"
    print("points      : %d  (%s)" % (len(df), os.path.basename(args.points)))
    print("id column   : %s" % id_col)

    states = gpd.read_file(BOUND)
    name_col = "NAME_1" if "NAME_1" in states.columns else states.columns[0]
    states = states[states[name_col].isin(NER_STATES)].copy()
    print("boundaries  : %d polygons for %d NER states (GADM has duplicates)"
          % (len(states), len(NER_STATES)))

    pts = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
        crs="EPSG:4326")

    # planar join in a local equal-area projection, then de-duplicate: the
    # duplicate Arunachal polygons overlap and would otherwise emit two rows
    joined = gpd.sjoin(pts.to_crs(AEQD),
                       states[[name_col, "geometry"]].to_crs(AEQD),
                       how="left", predicate="within")
    joined = joined.sort_values(name_col).drop_duplicates(subset=[id_col], keep="first")
    joined = joined.set_index(id_col).reindex(df[id_col].astype(str).values)

    got = joined[name_col].notna()
    print("matched     : %d / %d" % (int(got.sum()), len(df)))
    if (~got).any():
        print("  unmatched : %d (outside the NER state polygons)" % int((~got).sum()))

    # GADM spells "ArunachalPradesh" without the space, the GSI inventory spells
    # it with one. Both classes must use the same string or STATE stops working
    # as a grouping key.
    df["STATE"] = (joined[name_col].fillna("")
                   .str.replace("ArunachalPradesh", "Arunachal Pradesh",
                                regex=False).values)
    df.to_csv(args.points, index=False)
    print("\nupdated STATE in %s" % args.points)

    print("\n--- negatives per state ---")
    print(df["STATE"].fillna("(unmatched)").value_counts().to_string())

    if args.out_bhuvan:
        bh = pd.DataFrame({
            "SLIDE_NO": df[id_col].astype(str).values,
            "STATE": df["STATE"].fillna("").values,
            "lon": df[lon_col].values,
            "lat": df[lat_col].values,
        })
        bh.to_csv(args.out_bhuvan, index=False)
        print("\nwrote %s  (%d rows)" % (args.out_bhuvan, len(bh)))


if __name__ == "__main__":
    main()