"""
Hold one state out, train on the rest, and show what each model actually said.

The cross-validation numbers in metrics.json are the model's report card. This
script answers the next question: hand the model ground it has never seen and
check whether the answer is right.

Protocol
  1. every row of one state is removed from training
  2. the alert cut is chosen inside the remaining states, on blocks held out
     from fitting, so the cut is never tuned on the state being predicted
  3. the fitted model scores the held-out state
  4. the scores are compared against the recorded labels

Usage
  python scripts/check_predictions.py [state] [--show N]
"""

import argparse
import importlib.util
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location(
    "tlm", os.path.join(HERE, "train_landslide_model.py"))
tlm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tlm)

# Overridable so the same check can be run against any dataset version,
# e.g. TERRAPULSE_DATASET=.../landslide_dataset_v0.1.csv
DATASET = (os.environ.get("TERRAPULSE_DATASET")
           or os.path.join(REPO, "TERRAPULSE_DATA", "13_MODEL_DATASETS",
                           "landslide_dataset_v0.2_bhuvan.csv"))
N_CUT_FOLDS = 3


def blocks(df):
    lat = np.floor(df["lat"].values / tlm.BLOCK_DEG).astype(int)
    lon = np.floor(df["lon"].values / tlm.BLOCK_DEG).astype(int)
    return pd.Series(["b%d_%d" % (a, b) for a, b in zip(lat, lon)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("state", nargs="?", default="Sikkim")
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()

    df = pd.read_csv(DATASET)
    X, y, num_cols, cat_cols, feats, const, high = tlm.select_features(df)
    states = df["STATE"].astype(str).values

    held = states == args.state
    if held.sum() == 0:
        sys.exit("no rows for state %r. available: %s"
                 % (args.state, ", ".join(sorted(set(states)))))

    print("dataset        : %s" % os.path.basename(DATASET))
    print("held-out state : %s  (%d rows, %d landslides)"
          % (args.state, int(held.sum()), int(y[held].sum())))
    print("trained on     : %d rows from the other %d states"
          % (int((~held).sum()), len(set(states[~held]))))
    print("features       : %d" % len(feats))
    print()

    tr = ~held
    Xtr, ytr = X[tr], y[tr]
    grp = blocks(df)[tr]

    print("%-6s %6s %8s %8s %8s %8s %8s %8s" % (
        "model", "cut", "acc", "precis", "recall", "f1", "auc", "missed"))
    rows = []
    for name in ("rf", "xgb", "lgbm"):
        cuts = []
        sgkf = StratifiedGroupKFold(n_splits=N_CUT_FOLDS, shuffle=True,
                                    random_state=tlm.SEED)
        for fit_i, val_i in sgkf.split(Xtr, ytr, grp):
            probe = tlm.build_model(name, num_cols, cat_cols)
            probe.fit(Xtr.iloc[fit_i], ytr.iloc[fit_i])
            p_val = probe.predict_proba(Xtr.iloc[val_i])[:, 1]
            cuts.append(tlm.choose_threshold(ytr.iloc[val_i].values, p_val))
        cut = float(np.median(cuts))

        pipe = tlm.build_model(name, num_cols, cat_cols)
        pipe.fit(Xtr, ytr)
        p = pipe.predict_proba(X[held])[:, 1]
        yt = y[held].values
        yhat = (p >= cut).astype(int)

        tn, fp, fn, tp = confusion_matrix(yt, yhat, labels=[0, 1]).ravel()
        rows.append({"model": name, "cut": cut, "score": p, "yhat": yhat})
        print("%-6s %6.2f %8.4f %8.4f %8.4f %8.4f %8.4f %8d" % (
            name, cut, accuracy_score(yt, yhat),
            precision_score(yt, yhat, zero_division=0),
            recall_score(yt, yhat, zero_division=0),
            f1_score(yt, yhat, zero_division=0),
            roc_auc_score(yt, p), int(fn)))

    best = max(rows, key=lambda r: f1_score(y[held].values, r["yhat"],
                                            zero_division=0))
    print()
    print("--- %s, %d example points, %s ---" % (args.state, args.show,
                                                  best["model"]))
    order = np.argsort(-best["score"])
    sub = df[held].iloc[order][["SLIDE_NO", "STATE", "DISTRICT", "slope_deg",
                                "elevation_m"]].copy()
    sub["actual"] = y[held].values[order]
    sub["score"] = np.round(best["score"][order], 4)
    sub["said"] = np.where(best["yhat"][order] == 1, "landslide", "clear")
    sub["right?"] = np.where(best["yhat"][order] == y[held].values[order],
                             "yes", "NO")
    print(sub.head(args.show).to_string(index=False))
    print()
    wrong = int((best["yhat"] != y[held].values).sum())
    print("total wrong on unseen state: %d of %d  (%.1f%% right)"
          % (wrong, int(held.sum()), 100.0 * (1 - wrong / held.sum())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())