"""
How small can Random Forest get before it stops performing?

Why
  The saved Random Forest artifact is about 198 MB, against 2 MB for XGBoost and
  2 MB for LightGBM. TerraPulse is meant to push the model to field devices and
  run inference offline on a phone, and a 198 MB model does not fit that plan.

  The 0.003 F1 lead Random Forest has over the boosted models is inside the
  noise, so if it cannot be shrunk without losing that lead, the boosted models
  become the correct choice for this deployment.

Method
  Same three-way spatial block CV as the training run. Each configuration is
  scored identically, then refit on all rows and written to disk to measure the
  real artifact size.
"""

import importlib.util
import os
import tempfile

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "tlm", os.path.join(HERE, "train_landslide_model.py"))
tlm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tlm)

CONFIGS = [
    ("current (600 trees, leaf 2)", dict(n_estimators=600, min_samples_leaf=2)),
    ("300 trees, leaf 8", dict(n_estimators=300, min_samples_leaf=8)),
    ("200 trees, leaf 15, depth 16", dict(n_estimators=200, min_samples_leaf=15,
                                          max_depth=16)),
    ("120 trees, leaf 30, depth 12", dict(n_estimators=120, min_samples_leaf=30,
                                          max_depth=12)),
]


def make_factory(kw):
    def factory(name, num_cols, cat_cols):
        prep = ColumnTransformer([
            ("num", SimpleImputer(strategy="median"), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
             cat_cols),
        ])
        clf = RandomForestClassifier(n_jobs=-1, random_state=tlm.SEED, **kw)
        return Pipeline([("prep", prep), ("clf", clf)])
    return factory


def artifact_mb(model):
    fd, path = tempfile.mkstemp(suffix=".joblib")
    os.close(fd)
    try:
        joblib.dump(model, path)
        return os.path.getsize(path) / (1024.0 * 1024.0)
    finally:
        os.remove(path)


def main():
    df = pd.read_csv(tlm.DATASET)
    X, y, num_cols, cat_cols, feats, const, high = tlm.select_features(df)

    block_lat = np.floor(df["lat"].values / tlm.BLOCK_DEG).astype(int)
    block_lon = np.floor(df["lon"].values / tlm.BLOCK_DEG).astype(int)
    groups = pd.Series(["b%d_%d" % (a, b) for a, b in zip(block_lat, block_lon)])

    print("=" * 78)
    print("Random Forest size / performance trade-off")
    print("=" * 78)
    print("%-32s %7s %7s %7s %9s" % ("configuration", "F1", "recall", "AUC", "size MB"))
    print("-" * 78)

    original = tlm.build_model
    try:
        for label, kw in CONFIGS:
            tlm.build_model = make_factory(kw)
            folds, oof, pooled = tlm.run_block_cv("rf", X, y, groups,
                                                  num_cols, cat_cols)
            s = tlm.summarise(folds)

            final = make_factory(kw)("rf", num_cols, cat_cols)
            final.fit(X, y)
            mb = artifact_mb(final)

            print("%-32s %7.4f %7.4f %7.4f %9.1f"
                  % (label, s["f1"]["mean"], s["recall"]["mean"],
                     s["roc_auc"]["mean"], mb))
    finally:
        tlm.build_model = original

    print("-" * 78)
    print("reference: XGBoost F1 0.7165 / recall 0.8603 / AUC 0.7393 / 2.0 MB")
    print("           LightGBM F1 0.7152 / recall 0.8566 / AUC 0.7408 / 2.0 MB")


if __name__ == "__main__":
    main()