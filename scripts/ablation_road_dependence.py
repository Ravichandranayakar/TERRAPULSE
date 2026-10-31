"""
Ablation: how much of the baseline score depends on road information?

Why this exists
  In the first training run the road_fclass dummies took 0.28 of total XGBoost
  importance - more than any terrain variable. But road_fclass is partly a
  sampling artifact: the negatives were drawn uniformly along the road network,
  which over-represents long minor roads, while the GSI positives were recorded
  by field teams who reach landslides by road. If the headline score rests on
  that, it measures survey accessibility, not hazard.

  So the same block CV is re-run three ways.
"""

import importlib.util
import os
import numpy as np
import pandas as pd

SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "train_landslide_model.py")
spec = importlib.util.spec_from_file_location("tlm", SPEC)
tlm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tlm)

df = pd.read_csv(tlm.DATASET)
X_full, y, num_cols, cat_cols, feats, const, high = tlm.select_features(df)

block_lat = np.floor(df["lat"].values / tlm.BLOCK_DEG).astype(int)
block_lon = np.floor(df["lon"].values / tlm.BLOCK_DEG).astype(int)
groups = pd.Series(["b%d_%d" % (a, b) for a, b in zip(block_lat, block_lon)])

ROAD_COLS = ["road_fclass", "dist_road_m", "dist_road_km"]

variants = [
    ("A full baseline", X_full, num_cols, cat_cols),
    ("B no road_fclass",
     X_full.drop(columns=[c for c in cat_cols if c in X_full.columns]),
     [c for c in num_cols], []),
    ("C no road info at all",
     X_full.drop(columns=[c for c in ROAD_COLS if c in X_full.columns]),
     [c for c in num_cols if c not in ROAD_COLS], []),
]

print("=" * 74)
print("XGBoost, identical spatial block CV, road information removed")
print("=" * 74)
print("%-24s %8s %8s %8s %8s" % ("variant", "auc", "avgP", "prec", "rec"))
for label, Xv, nv, cv_ in variants:
    folds, oof, pooled = tlm.run_block_cv("xgb", Xv, y, groups, nv, cv_)
    s = tlm.summarise(folds)
    print("%-24s %8.4f %8.4f %8.4f %8.4f"
          % (label, s["roc_auc"]["mean"], s["avg_precision"]["mean"],
             s["precision"]["mean"], s["recall"]["mean"]))