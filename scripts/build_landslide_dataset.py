"""
Stack the positive and negative feature tables into one training dataset.

Inputs
  13_MODEL_DATASETS/landslide_features_positive.csv   (landslide = 1)
  13_MODEL_DATASETS/landslide_features_negative.csv   (landslide = 0)

Why a separate script
  The two tables are built by the same merge script, but they must still be
  checked for structural equality before stacking. If a column is present for
  one class and absent for the other, a model will learn "value present" as if
  it were the answer. That is leakage, and it is silent - so it is screened for
  explicitly here and never assumed away.

Output
  13_MODEL_DATASETS/landslide_dataset_v0.1.csv
  13_MODEL_DATASETS/landslide_dataset_v0.1_audit.txt
"""

import io
import os
import sys
import numpy as np
import pandas as pd

ROOT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA"
OUT_DIR = os.path.join(ROOT, "13_MODEL_DATASETS")
POS_CSV = os.path.join(OUT_DIR, "landslide_features_positive.csv")
NEG_CSV = os.path.join(OUT_DIR, "landslide_features_negative.csv")
OUT_CSV = os.path.join(OUT_DIR, "landslide_dataset_v0.1.csv")
AUDIT_TXT = os.path.join(OUT_DIR, "landslide_dataset_v0.1_audit.txt")

# Columns that exist for positives only because a landslide has a recorded event
# year. Negatives have no event, so these are structurally absent for them and
# must never reach the model.
LEAKY_BY_DESIGN = [
    "event_year", "year_source",
    "rain_annual_mm", "rain_monsoon_mm",
    "rain_monsoon_max1d_mm", "rain_monsoon_max5d_mm",
    "rain_anomaly", "rain_monsoon_anomaly",
]

# Identity / provenance columns. Not features, kept for traceability only.
ID_COLS = ["point_id", "SLIDE_NO", "STATE", "DISTRICT", "INITIATION",
           "lon", "lat", "dem_tile", "edge_pixel"]

lines = []


def say(msg=""):
    print(msg)
    lines.append(msg)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    pos = pd.read_csv(POS_CSV)
    neg = pd.read_csv(NEG_CSV)

    say("positive rows : %d" % len(pos))
    say("negative rows : %d" % len(neg))

    if list(pos.columns) != list(neg.columns):
        only_p = [c for c in pos.columns if c not in neg.columns]
        only_n = [c for c in neg.columns if c not in pos.columns]
        sys.exit("COLUMN MISMATCH\n  only in positives: %s\n  only in negatives: %s"
                 % (only_p, only_n))
    say("column check  : identical (%d columns)" % len(pos.columns))

    if int(pos["landslide"].sum()) != len(pos) or int(neg["landslide"].sum()) != 0:
        sys.exit("label column is not consistent with the two source files")
    say("label check   : positives all 1, negatives all 0")

    dup = set(pos["point_id"]) & set(neg["point_id"])
    if dup:
        sys.exit("point_id collision between classes: %d" % len(dup))
    say("point_id check: unique across both classes")

    df = pd.concat([pos, neg], axis=0, ignore_index=True)
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    say("stacked+shuffled: %d rows x %d cols" % df.shape)

    # ---- leakage screen ----
    say()
    say("--- leakage screen (columns missing for one class only) ---")
    hits = []
    for c in df.columns:
        if c in ID_COLS or c == "landslide":
            continue
        mp = df.loc[df.landslide == 1, c].isna().mean()
        mn = df.loc[df.landslide == 0, c].isna().mean()
        if (mp > 0.99) != (mn > 0.99):
            hits.append((c, mp, mn))
    if hits:
        for c, mp, mn in hits:
            say("  LEAK  %-24s missing pos %6.1f%%  neg %6.1f%%" % (c, 100 * mp, 100 * mn))
    else:
        say("  none")

    say()
    say("--- columns flagged leaky by design (must be dropped before training) ---")
    for c in LEAKY_BY_DESIGN:
        if c in df.columns:
            mp = df.loc[df.landslide == 1, c].isna().mean()
            mn = df.loc[df.landslide == 0, c].isna().mean()
            say("  %-24s missing pos %6.1f%%  neg %6.1f%%" % (c, 100 * mp, 100 * mn))

    # ---- missingness ----
    say()
    say("--- missing values, columns with any gap ---")
    mv = df.isna().sum()
    mv = mv[mv > 0].sort_values(ascending=False)
    if not len(mv):
        say("  none")
    for c, v in mv.items():
        say("  %-24s %5d  (%.2f%%)" % (c, v, 100 * v / len(df)))

    # ---- class separation check ----
    say()
    say("--- feature medians by class (a huge gap means the feature is suspect) ---")
    skip = set(ID_COLS) | set(LEAKY_BY_DESIGN) | {"landslide", "low_slope_review"}
    rows = []
    for c in df.columns:
        if c in skip:
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        a = df.loc[df.landslide == 1, c].median()
        b = df.loc[df.landslide == 0, c].median()
        if pd.isna(a) or pd.isna(b):
            continue
        denom = max(abs(a), abs(b), 1e-9)
        rows.append((c, a, b, abs(a - b) / denom))
    rows.sort(key=lambda r: -r[3])
    say("  %-24s %12s %12s %8s" % ("feature", "landslide", "negative", "reldiff"))
    for c, a, b, d in rows:
        say("  %-24s %12.3f %12.3f %7.1f%%" % (c, a, b, 100 * d))

    df.to_csv(OUT_CSV, index=False)
    say()
    say("wrote %s" % OUT_CSV)

    with io.open(AUDIT_TXT, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote %s" % AUDIT_TXT)


if __name__ == "__main__":
    main()