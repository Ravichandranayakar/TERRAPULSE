"""
Operating points for the trained landslide model.

What this answers
  The model gives each point a score from 0 to 1. An operator picks the cut:
  warn above it, stay quiet below. Moving that cut trades missed landslides
  against false alarms. This script prints what each setting actually costs.

Why out-of-fold scores and not the saved model
  The saved model was fitted on all 17,092 rows, so scoring those same rows
  would report how well it memorised them. Every number here comes from
  spatial block cross-validation instead: each point is scored by a model that
  never saw its block. Same folds as the training run.

Output
  models/<version>/oof_predictions.csv    per-point held-out score
  and a printed operating-point table.
"""

import argparse
import importlib.util
import io
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "train_landslide_model.py")
spec = importlib.util.spec_from_file_location("tlm", SPEC)
tlm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tlm)

CUTS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]


def main():
    ap = argparse.ArgumentParser()
    # default to whichever model the training run actually saved, so this
    # script cannot drift out of step with the artifact
    schema_p = os.path.join(tlm.ART_DIR, "feature_schema.json")
    saved = "xgb"
    if os.path.exists(schema_p):
        saved = json.load(io.open(schema_p, encoding="utf-8"))["model"]
    ap.add_argument("--model", default=saved,
                    choices=["logreg", "rf", "xgb", "lgbm"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    df = pd.read_csv(tlm.DATASET)
    y = df["landslide"].astype(int)
    X, y, num_cols, cat_cols, feats, const, high = tlm.select_features(df)

    block_lat = np.floor(df["lat"].values / tlm.BLOCK_DEG).astype(int)
    block_lon = np.floor(df["lon"].values / tlm.BLOCK_DEG).astype(int)
    groups = pd.Series(["b%d_%d" % (a, b) for a, b in zip(block_lat, block_lon)])

    print("scoring every point with a model that never saw its block ...")
    folds, oof, pooled = tlm.run_block_cv(args.model, X, y, groups, num_cols, cat_cols)

    valid = ~np.isnan(oof)
    yv = y.values[valid]
    pv = oof[valid]
    print("held-out points scored: %d of %d" % (int(valid.sum()), len(oof)))
    print("threshold-free quality: ROC-AUC %.4f   Average Precision %.4f"
          % (pooled["roc_auc"], pooled["avg_precision"]))

    print()
    print("=" * 84)
    print("ALERT LEVEL TABLE  (model = %s, all numbers from held-out spatial blocks)" % args.model)
    print("=" * 84)
    print("  %5s | %8s | %8s | %8s | %7s | %7s | %7s"
          % ("cut", "warned", "caught", "missed", "recall", "precis", "F1"))
    print("  " + "-" * 78)
    for t in CUTS:
        m = tlm.score_at(yv, pv, t)
        warned = m["tp"] + m["fp"]
        print("  %5.2f | %8d | %8d | %8d | %7.3f | %7.3f | %7.3f"
              % (t, warned, m["tp"], m["fn"], m["recall"], m["precision"], m["f1"]))

    f1_cut = tlm.choose_threshold(yv, pv)
    mf1 = tlm.score_at(yv, pv, f1_cut)
    print("  " + "-" * 78)
    print("  F1-optimal cut %.2f   recall %.3f   precision %.3f   f1 %.3f"
          % (f1_cut, mf1["recall"], mf1["precision"], mf1["f1"]))
    print()
    print("  recall    = of all real landslides, the share we warned about")
    print("  precision = of all our warnings, the share that were real")
    print("  missed    = real landslides that produced NO warning")

    print()
    print("--- what the choice looks like in practice ---")
    # The deployed cut is whatever the training run chose on validation blocks,
    # taken from the folds above. It used to be typed in here as 0.53, which was
    # the old training-tuned value and no longer reflects what the model does.
    deployed = float(np.median([f["threshold"] for f in folds]))
    m = tlm.score_at(yv, pv, deployed)
    print("  %-38s cut %.2f -> catch %3.0f%%, %4d false alarms per %d warnings"
          % ("deployed (chosen on validation)", deployed, 100 * m["recall"],
             m["fp"], m["tp"] + m["fp"]))
    for label, cut_t in [("cautious (few false alarms)", 0.70),
                         ("safety-first (catch almost everything)", 0.20)]:
        m = tlm.score_at(yv, pv, cut_t)
        print("  %-38s cut %.2f -> catch %3.0f%%, %4d false alarms per %d warnings"
              % (label, cut_t, 100 * m["recall"], m["fp"], m["tp"] + m["fp"]))

    out = args.out or os.path.join(tlm.ART_DIR, "oof_predictions.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    res = df[["point_id", "SLIDE_NO", "STATE", "lon", "lat", "landslide"]].copy()
    res["score"] = oof
    res["held_out"] = valid.astype(int)
    res.to_csv(out, index=False)
    print()
    print("wrote %s" % out)
    print("that file holds one held-out score per point, so the table above can be")
    print("recomputed later without retraining anything.")


if __name__ == "__main__":
    main()