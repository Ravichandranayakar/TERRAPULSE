"""
Attach Bhuvan geomorphology and lineament features to the landslide dataset.

Why
  The base model sees terrain (slope, elevation, curvature) but not the rock or
  the structure. Geomorphology says what landform the point sits on and
  lineaments say how far it is from a fault, joint or fracture trace. Both are
  standard susceptibility inputs in published landslide work, and both are
  static: they describe the ground, not the weather, so they can be stored once
  and reused at inference instead of refetched.

Source
  GSI / ISRO data served through the Bhuvan WFS, pulled per point by
  scripts/bhuvan_fetch_points.py into:
    bhuvan_out.csv            the 8,546 positive points (recorded landslides)
    bhuvan_out_negative.csv   the 8,546 generated negatives

Join
  On (SLIDE_NO, lon, lat), not on row order. The Bhuvan pull returns its own
  ordering, so a positional join would silently line the wrong ground up with
  the wrong label. Both files carry the real identifier in `id`.

Missing values are kept as missing
  Geomorphology is absent for about 25% of positives and 14% of negatives, and
  lineaments for about 46% of both, because the Bhuvan layer does not cover
  every location. That gap is spatial, not random, so it is flagged with an
  indicator column rather than papered over with an imputation. The training
  script medians the numeric gaps and offers the flag alongside.

Output
  13_MODEL_DATASETS/landslide_dataset_v0.2_bhuvan.csv
""" 
import io
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "TERRAPULSE_DATA", "13_MODEL_DATASETS")
BASE = os.path.join(DATA_DIR, "landslide_dataset_v0.1.csv")
SOURCES = [("bhuvan_out.csv", 1), ("bhuvan_out_negative.csv", 0)]
OUT = os.path.join(DATA_DIR, "landslide_dataset_v0.2_bhuvan.csv")
REPORT = os.path.join(DATA_DIR, "landslide_dataset_v0.2_bhuvan_audit.txt")

KEY = ["SLIDE_NO", "lon", "lat"]

# Feature columns the model may use.
FEATURE_COLS = ["geomorph_l1", "geomorph_l2", "lineament_dist_km",
                "lineament_n", "lineament_mag", "geomorph_des", "lineament_des"]
# Carried for traceability only. state_code is the state spelled as a code, and
# STATE is already excluded from training so the leave-one-state-out pass still
# means something; keeping the code as a feature would undo that.
PROVENANCE_COLS = ["bhuvan_state_code", "bhuvan_status"]

lines = []


def say(msg=""):
    print(msg)
    lines.append(str(msg))


def canonical_text(series):
    """Fold spelling variants to the most common form.

    Bhuvan writes some labels two ways ("Drainage parallel" and "Drainage
    Parallel"). Left alone those become two categories describing one landform.
    """
    stripped = series.astype("string").str.strip()
    variants = {}
    for value, count in stripped.value_counts().items():
        key = value.lower()
        if key not in variants or count > variants[key][0]:
            variants[key] = (count, value)
    return stripped.map(
        lambda v: variants.get(v.lower(), (0, v))[1] if pd.notna(v) else v)


def load_source(name, label):
    path = os.path.join(DATA_DIR, name)
    frame = pd.read_csv(path)
    frame = frame.rename(columns={"id": "SLIDE_NO", "state_code": "bhuvan_state_code",
                                  "status": "bhuvan_status"})
    frame["landslide"] = label
    keep = KEY + ["bhuvan_state_code", "bhuvan_status"] + FEATURE_COLS
    frame = frame[[c for c in keep if c in frame.columns]]

    before = len(frame)
    frame = frame.drop_duplicates(subset=KEY, keep="first")
    if before != len(frame):
        say("  %s: dropped %d duplicate (SLIDE_NO, lon, lat) rows"
            % (name, before - len(frame)))
    return frame


def main():
    say("Bhuvan enrichment")
    base = pd.read_csv(BASE)
    say("  base: %s  %d rows x %d cols"
        % (os.path.basename(BASE), len(base), base.shape[1]))

    bhuvan = pd.concat([load_source(n, l) for n, l in SOURCES], ignore_index=True)
    say("  bhuvan: %d rows covering %d points"
        % (len(bhuvan), bhuvan["SLIDE_NO"].nunique()))

    for col in ("geomorph_des", "lineament_des"):
        bhuvan[col] = canonical_text(bhuvan[col])

    # many_to_one: the base carries five positive points twice (same SLIDE_NO,
    # same coordinates, same label). Bhuvan returned each of those once. Both
    # copies get the same ground description, so the enrichment does not change
    # the row count and does not invent or drop a record.
    merged = base.merge(bhuvan, on=KEY, how="left", validate="many_to_one")

    if len(merged) != len(base):
        raise SystemExit("merge changed the row count: %d -> %d"
                         % (len(base), len(merged)))

    unmatched = merged["geomorph_l1"].isna() & merged["lineament_dist_km"].isna()
    say()
    say("  rows matched to a Bhuvan point : %d of %d"
        % (int(bhuvan["SLIDE_NO"].isin(base["SLIDE_NO"]).sum()), len(base)))
    say("  no geomorphology at all        : %d (%.1f%%)"
        % (int(unmatched.sum()), 100.0 * unmatched.mean()))
    say()
    say("  coverage by label")
    for label, name in ((1, "landslide"), (0, "no-landslide")):
        part = merged[merged["landslide"] == label]
        say("    %-13s geomorph %.1f%%   lineament %.1f%%   (n=%d)"
            % (name, 100.0 * part["geomorph_l1"].notna().mean(),
               100.0 * part["lineament_dist_km"].notna().mean(), len(part)))

    # A lineament count above zero with no distance would mean the distance is
    # missing even though lineaments exist nearby, which is a different problem
    # from the layer simply not covering the point.
    odd = ((merged["lineament_n"].fillna(0) > 0)
           & merged["lineament_dist_km"].isna())
    if odd.any():
        say("  note: %d points report lineaments nearby but no distance" % int(odd.sum()))
    say()
    say("  lineaments mapped at the point : %d of %d"
        % (int(merged["lineament_dist_km"].notna().sum()), len(merged)))
    say("  median distance to a lineament : %.3f km"
        % float(merged["lineament_dist_km"].median()))

    merged.to_csv(OUT, index=False)
    say()
    say("  wrote %s" % os.path.relpath(OUT, REPO))
    say("  %d rows x %d cols (+%d feature cols, +%d provenance cols)"
        % (len(merged), merged.shape[1], len(FEATURE_COLS), len(PROVENANCE_COLS)))

    with io.open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())