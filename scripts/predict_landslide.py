"""
Score points with the trained landslide model.

Usage
  python scripts/predict_landslide.py
      scores the assembled dataset as a demonstration
  python scripts/predict_landslide.py <input.csv> [<output.csv>]

Input must already carry the feature columns listed in the artifact's
feature_schema.json. The model does NOT take raw coordinates: a brand-new
location needs terrain, rainfall, land cover, soil and distance features
extracted first, which is what the extract_*.py scripts do.

What the score means
  A relative ranking of landslide susceptibility, 0 to 1. It is NOT a
  calibrated probability: the model was trained on a 1:1 balanced sample, so
  the base rate is 0.5, which is not the real-world event rate.
"""

import argparse
import io
import json
import os
import sys

import importlib.util

import joblib
import numpy as np
import pandas as pd

# The derived columns (aspect_sin/aspect_cos, the missingness flags) are built
# at training time, not stored in the CSV. Importing the training module means
# prediction uses byte-for-byte the same derivation.
_spec = importlib.util.spec_from_file_location(
    "tlm", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "train_landslide_model.py"))
tlm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tlm)

REPO = r"C:\Users\Ravichandran\Downloads\TERRAPULSE"
# Overridable so any saved version can be scored without editing the file,
# e.g. TERRAPULSE_MODEL_DIR=models/landslide_bhuvan_v0.2
ART_DIR = (os.environ.get("TERRAPULSE_MODEL_DIR")
           or os.path.join(REPO, "models", "landslide_v0.1"))
DEFAULT_IN = (os.environ.get("TERRAPULSE_DATASET")
              or os.path.join(REPO, "TERRAPULSE_DATA", "13_MODEL_DATASETS",
                              "landslide_dataset_v0.1.csv"))

# carried through to the output when present; never used as features
PASSTHROUGH = ["point_id", "SLIDE_NO", "STATE", "lon", "lat"]


def load_artifact():
    schema_p = os.path.join(ART_DIR, "feature_schema.json")
    thr_p = os.path.join(ART_DIR, "thresholds.json")
    for p in (schema_p, thr_p):
        if not os.path.exists(p):
            sys.exit("missing %s - run scripts/train_landslide_model.py first" % p)
    schema = json.load(io.open(schema_p, encoding="utf-8"))
    thresholds = json.load(io.open(thr_p, encoding="utf-8"))
    model_p = os.path.join(ART_DIR, "%s.joblib" % schema["model"])
    if not os.path.exists(model_p):
        sys.exit("missing model file %s" % model_p)
    return joblib.load(model_p), schema, thresholds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default=DEFAULT_IN)
    ap.add_argument("output", nargs="?")
    ap.add_argument("--cut", type=float, default=0.0,
                    help="warn above this score. Default: the balanced cut "
                         "recorded in thresholds.json")
    args = ap.parse_args()

    model, schema, thresholds = load_artifact()
    feats = schema["numeric_features"] + schema["categorical_features"]

    if not os.path.exists(args.input):
        sys.exit("input not found: %s" % args.input)
    df = tlm.derive_features(pd.read_csv(args.input))

    missing = [c for c in feats if c not in df.columns]
    if missing:
        sys.exit("input is missing %d required feature column(s):\n  %s\n"
                 "These come from the extract_*.py scripts; the model does not "
                 "accept raw coordinates." % (len(missing), ", ".join(missing)))

    cut = args.cut or float(thresholds.get("f1_optimal_mean_over_folds", 0.5))

    print("model      : %s   (%s)" % (schema["model"], schema["artifact_version"]))
    print("input      : %s  (%d rows)" % (os.path.basename(args.input), len(df)))
    print("features   : %d" % len(feats))
    print("alert cut  : %.2f" % cut)

    score = model.predict_proba(df[feats])[:, 1]
    out = pd.DataFrame({"score": np.round(score, 4),
                        "warned": (score >= cut).astype(int)})
    for c in PASSTHROUGH:
        if c in df.columns:
            out.insert(0, c, df[c].values)

    n_warn = int(out["warned"].sum())
    print()
    print("scored     : %d points" % len(out))
    print("warned     : %d  (%.1f%%)" % (n_warn, 100 * n_warn / len(out)))
    print("quiet      : %d" % (len(out) - n_warn))

    print()
    print("--- highest 10 scores ---")
    show = ["SLIDE_NO", "STATE", "score", "warned"]
    show = [c for c in show if c in out.columns]
    print(out.sort_values("score", ascending=False).head(10)[show].to_string(index=False))

    print()
    print("--- lowest 10 scores ---")
    print(out.sort_values("score").head(10)[show].to_string(index=False))

    # if the labels are present the caller is scoring known points, so an
    # accuracy figure here measures memorisation, not performance
    if "landslide" in df.columns:
        y = df["landslide"].astype(int).values
        yhat = out["warned"].values
        tp = int(((y == 1) & (yhat == 1)).sum())
        fp = int(((y == 0) & (yhat == 1)).sum())
        fn = int(((y == 1) & (yhat == 0)).sum())
        tn = int(((y == 0) & (yhat == 0)).sum())
        print()
        print("--- agreement with the known labels ---")
        print("  caught %d   missed %d   false alarms %d   correct quiet %d"
              % (tp, fn, fp, tn))
        print("  This model was fitted on these same rows, so these figures are")
        print("  OPTIMISTIC. For honest performance use the held-out numbers from")
        print("  scripts/model_operating_points.py.")

    print()
    print("The score ranks susceptibility. It is not a calibrated probability,")
    print("because the training sample is 1:1 balanced rather than the real event rate.")

    if args.output:
        out.to_csv(args.output, index=False)
        print()
        print("wrote %s" % args.output)


if __name__ == "__main__":
    main()