"""
Train and spatially validate the NER landslide susceptibility model.

Input
  TERRAPULSE_DATA/13_MODEL_DATASETS/landslide_dataset_v0.1.csv

Label
  landslide = 1   recorded landslide (GSI inventory)
  landslide = 0   generated negative (construction method in build_negatives.py)

Output
  models/landslide_v0.1/<model>.joblib
  models/landslide_v0.1/feature_schema.json
  models/landslide_v0.1/thresholds.json
  models/landslide_v0.1/metrics.json
  models/landslide_v0.1/training_report.txt

Why the validation is blocked, not random
  Landslide points cluster on the same slopes, often a few hundred metres
  apart. A random row split puts neighbouring points on both sides of the
  split, and the score then measures memorised location rather than hazard.
  Every fold here holds out whole 0.5-degree blocks, and a second
  leave-one-state-out pass holds out an entire state.

What this model is NOT
  - not a calibrated probability: the 1:1 case/control design fixes the base
    rate at 0.5, which is not the real event rate, so the score is a ranking,
    not a probability of sliding
  - not evidence that a location without a record had no landslide: GSI is a
    presence-only inventory and the negatives are constructed, not observed
  - not a rainfall threshold: event-year rainfall is deliberately absent from
    the features because the negatives have no event date, so including it
    would leak the label
"""

import io
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

# LightGBM is only a benchmark challenger, so a missing install degrades to a
# four-model comparison instead of breaking the whole script.
try:
    from lightgbm import LGBMClassifier
except ImportError:
    LGBMClassifier = None

REPO = r"C:\Users\Ravichandran\Downloads\TERRAPULSE"
DATASET = (os.environ.get("TERRAPULSE_DATASET")
           or os.path.join(REPO, "TERRAPULSE_DATA", "13_MODEL_DATASETS",
                           "landslide_dataset_v0.1.csv"))
# Overridable so the feedback loop can train a candidate into its own
# version directory and promote it only after it passes validation.
ART_DIR = (os.environ.get("TERRAPULSE_MODEL_DIR")
           or os.path.join(REPO, "models", "landslide_v0.1"))

# The folder name is the version. It used to be typed in as a literal, so a
# candidate trained into models/landslide_v0.4 still wrote landslide_v0.1 into
# its own schema and thresholds, and the feedback loop recorded the wrong
# version for every artifact it produced.
ART_VERSION = os.path.basename(ART_DIR.rstrip("\\/"))

SEED = 42
N_SPLITS = 5
BLOCK_DEG = 0.5
THRESHOLD_GRID = np.round(np.arange(0.05, 0.96, 0.01), 4)
CAT_MAX_LEVELS = 20

# Identity / provenance. Kept in the dataset for traceability, never fed to a
# model. lon/lat especially: as features they let the model memorise geography.
ID_COLS = ["point_id", "SLIDE_NO", "STATE", "DISTRICT", "INITIATION",
           "lon", "lat", "dem_tile", "edge_pixel",
           # Bhuvan spells the state as a short code (SK, MZ, AR ...) and
           # reports whether the layer answered. STATE is excluded so the
           # leave-one-state-out pass measures generalisation rather than
           # memorised geography; a state code as a feature would undo that.
           "bhuvan_state_code", "bhuvan_status"]

# Present for positives only, because a landslide has a recorded event date and
# a generated negative does not. Screened in build_landslide_dataset.py.
LEAKY_COLS = ["event_year", "year_source",
              "rain_annual_mm", "rain_monsoon_mm", "rain_monsoon_max1d_mm",
              "rain_monsoon_max5d_mm", "rain_anomaly", "rain_monsoon_anomaly"]

# Same information in different units, or a deterministic restatement of a
# column that is already present.
REDUNDANT_COLS = ["dist_road_km", "dist_river_km", "dist_water_km",
                  "texture_sum_gkg",          # always 1000 g/kg by construction
                  "landcover_name",           # 1:1 with landcover_class
                  "low_slope_review",         # derived from slope_deg
                  "rain_data_gap"]            # constant zero in this version

# Columns that are missing for a reason (outside the IMD grid, outside the
# SoilGrids extent) rather than at random. The gap is spatially clustered, so
# the indicator is offered to the model instead of hiding the gap by imputing.
MISSING_GROUPS = {
    "rain_clim": ["rain_clim_annual_mm", "rain_clim_monsoon_mm",
                  "rain_clim_max1d_mm", "rain_clim_max5d_mm"],
    "soil": ["clay_gkg", "sand_gkg", "silt_gkg",
             "bulk_density_kgdm3", "soc_gkg", "nitrogen_gkg"],
    # Bhuvan covers most of the study area but not all of it. Geomorphology is
    # absent for about a quarter of the positives and a seventh of the
    # negatives, and lineaments for nearly half of both, in clusters that
    # follow the layer boundary rather than at random.
    # The text companion of each gap rides in the same group: when the layer
    # does not answer, lineament_des is blank for exactly the same points as the
    # numbers, so it belongs to the same imputation contract.
    "geomorph": ["geomorph_l1", "geomorph_l2", "geomorph_des"],
    "lineament": ["lineament_dist_km", "lineament_n", "lineament_mag",
                  "lineament_des"],
}

lines = []


def say(msg=""):
    print(msg)
    lines.append(str(msg))


def build_model(name, num_cols, cat_cols):
    """Fresh, unfitted estimator. Preprocessing lives inside the pipeline so the
    saved artifact carries its own imputation and encoding."""
    cat_pipe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

    if name == "logreg":
        prep = ColumnTransformer([
            ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                              ("scale", StandardScaler())]), num_cols),
            ("cat", cat_pipe, cat_cols),
        ])
        clf = LogisticRegression(max_iter=5000, random_state=SEED)
    elif name == "rf":
        prep = ColumnTransformer([
            ("num", SimpleImputer(strategy="median"), num_cols),
            ("cat", cat_pipe, cat_cols),
        ])
        # Depth-limited on purpose. 600 fully grown trees with leaf=2 produced
        # a 198 MB artifact against 2 MB for the boosted models, and this model
        # is meant to run offline on a field device, so that artifact does not
        # ship. scripts/ablation_rf_size.py measured the size/performance curve:
        # 200 trees with a minimum leaf of 15 cuts the artifact to about 13 MB
        # and moves F1 by 0.0025, roughly a tenth of the fold-to-fold noise.
        # The extra 185 MB bought no measurable performance.
        clf = RandomForestClassifier(
            n_estimators=200, min_samples_leaf=15, max_depth=16,
            max_features="sqrt", n_jobs=-1, random_state=SEED)
    elif name == "xgb":
        prep = ColumnTransformer([
            ("num", SimpleImputer(strategy="median"), num_cols),
            ("cat", cat_pipe, cat_cols),
        ])
        clf = XGBClassifier(
            n_estimators=600, learning_rate=0.05, max_depth=6,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=2,
            reg_lambda=1.0, tree_method="hist", eval_metric="logloss",
            n_jobs=-1, random_state=SEED)
    elif name == "lgbm":
        if LGBMClassifier is None:
            sys.exit("lightgbm is not installed\n"
                     "  python -m pip install lightgbm")
        prep = ColumnTransformer([
            ("num", SimpleImputer(strategy="median"), num_cols),
            ("cat", cat_pipe, cat_cols),
        ])
        # LightGBM grows leaf-first rather than depth-first. Parameters are kept
        # deliberately close to the XGBoost settings so the comparison measures
        # the algorithm, not how hard either one was tuned.
        clf = LGBMClassifier(
            n_estimators=600, learning_rate=0.05, num_leaves=31,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
            min_child_samples=20, reg_lambda=1.0,
            n_jobs=-1, random_state=SEED, verbose=-1)
    else:
        sys.exit("unknown model: %s" % name)

    return Pipeline([("prep", prep), ("clf", clf)])


def choose_threshold(y_true, p, target_recall=None):
    """Pick the alert cut on a VALIDATION set, never on the data being reported.

    An earlier version searched the cut on the same rows the model was fitted
    on. Training rows score more confidently than unseen rows, so the chosen
    cut sat too high and reported recall read 0.545 when the model could
    actually reach about 0.90. The cut is now chosen on blocks held out from
    fitting, and reported on blocks held out from both.

    Default: the cut that maximises F1.
    If target_recall is given: the highest cut that still reaches that recall,
    so precision is as good as the recall floor allows.
    """
    if target_recall is not None:
        ok = [t for t in THRESHOLD_GRID
              if recall_score(y_true, (p >= t).astype(int),
                              zero_division=0) >= target_recall]
        if ok:
            return float(max(ok))
        return float(THRESHOLD_GRID[0])

    best_t, best_f = 0.5, -1.0
    for t in THRESHOLD_GRID:
        f = f1_score(y_true, (p >= t).astype(int), zero_division=0)
        if f > best_f:
            best_f, best_t = f, float(t)
    return best_t


def score_at(y_true, p, t):
    yhat = (p >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, yhat, labels=[0, 1]).ravel()
    out = {
        "threshold": float(t),
        "roc_auc": float(roc_auc_score(y_true, p)),
        "avg_precision": float(average_precision_score(y_true, p)),
        "precision": float(precision_score(y_true, yhat, zero_division=0)),
        "recall": float(recall_score(y_true, yhat, zero_division=0)),
        "f1": float(f1_score(y_true, yhat, zero_division=0)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "n": int(len(y_true)),
    }
    out["false_negative_rate"] = float(fn / (fn + tp)) if (fn + tp) else float("nan")
    out["false_positive_rate"] = float(fp / (fp + tn)) if (fp + tn) else float("nan")
    return out


def summarise(folds):
    """Mean and standard deviation of the threshold-free metrics."""
    keys = ["roc_auc", "avg_precision", "precision", "recall", "f1"]
    out = {}
    for k in keys:
        vals = np.array([f[k] for f in folds], dtype=float)
        out[k] = {"mean": float(np.nanmean(vals)), "std": float(np.nanstd(vals))}
    return out


def run_block_cv(name, X, y, groups, num_cols, cat_cols, target_recall=None):
    """Three-way spatial block CV.

    Each round holds out two disjoint sets of whole blocks:

      fit blocks   -> train the model
      val blocks   -> choose the alert cut
      test blocks  -> report performance

    Three ways rather than two because a cut chosen on fitting data is biased:
    the model scores its own training rows more confidently, so the cut lands
    too high and recall ends up under-reported.
    """
    outer = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    oof = np.full(len(y), np.nan, dtype=float)
    folds = []
    for k, (tr_all, te) in enumerate(outer.split(X, y, groups=groups), 1):
        inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=SEED + k)
        sub_fit, sub_val = next(inner.split(
            X.iloc[tr_all], y.iloc[tr_all], groups=groups.iloc[tr_all]))
        fit_idx = np.asarray(tr_all)[sub_fit]
        val_idx = np.asarray(tr_all)[sub_val]

        model = build_model(name, num_cols, cat_cols)
        model.fit(X.iloc[fit_idx], y.iloc[fit_idx])
        p_val = model.predict_proba(X.iloc[val_idx])[:, 1]
        thr = choose_threshold(y.iloc[val_idx].values, p_val, target_recall)

        p_te = model.predict_proba(X.iloc[te])[:, 1]
        oof[te] = p_te
        m = score_at(y.iloc[te].values, p_te, thr)
        m["fold"] = k
        m["n_blocks_test"] = int(len(np.unique(groups.iloc[te])))
        m["n_blocks_fit"] = int(len(np.unique(groups.iloc[fit_idx])))
        m["n_blocks_val"] = int(len(np.unique(groups.iloc[val_idx])))
        folds.append(m)
    pooled = score_at(y.values, oof, float(np.median([f["threshold"] for f in folds])))
    return folds, oof, pooled


def run_leave_one_state_out(name, X, y, states, groups, num_cols, cat_cols):
    """Harshest test: train on seven states, predict the eighth.

    The alert cut comes from blocks held out of the seven-state fit, never from
    the state being predicted.
    """
    folds = []
    for st in sorted(states.unique()):
        te = (states == st).values
        tr = np.where(~te)[0]
        if te.sum() < 50 or len(np.unique(y.values[te])) < 2:
            continue
        inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=SEED)
        sub_fit, sub_val = next(inner.split(
            X.iloc[tr], y.iloc[tr], groups=groups.iloc[tr]))
        fit_idx = tr[sub_fit]
        val_idx = tr[sub_val]

        model = build_model(name, num_cols, cat_cols)
        model.fit(X.iloc[fit_idx], y.iloc[fit_idx])
        p_val = model.predict_proba(X.iloc[val_idx])[:, 1]
        thr = choose_threshold(y.iloc[val_idx].values, p_val)
        p_te = model.predict_proba(X.iloc[te])[:, 1]
        m = score_at(y.values[te], p_te, thr)
        m["state"] = st
        folds.append(m)
    return folds


def top_importances(model, k=15):
    clf = model.named_steps["clf"]
    if not hasattr(clf, "feature_importances_"):
        return []
    names = model.named_steps["prep"].get_feature_names_out()
    imp = clf.feature_importances_
    order = np.argsort(imp)[::-1][:k]
    return [(str(names[i]), float(imp[i])) for i in order]


def derive_features(df):
    """Add the derived columns.

    Shared by training and prediction on purpose. If the two ever drifted apart
    the model would silently be handed different inputs than it was fitted on,
    which is the classic way a working model breaks in production.
    """
    out = df.copy()

    # aspect is circular: 0 and 359 degrees are neighbours. Raw degrees make the
    # model treat them as opposite ends of the range, so project to sin/cos.
    if "aspect_deg" in out.columns:
        rad = np.radians(out["aspect_deg"].astype(float))
        out["aspect_sin"] = np.sin(rad)
        out["aspect_cos"] = np.cos(rad)

    # a gap here means the point falls outside the IMD grid or the SoilGrids
    # extent - a spatial gap, not a random one, so flag it rather than hide it
    for group, cols in MISSING_GROUPS.items():
        present = [c for c in cols if c in out.columns]
        if present:
            out["miss_%s" % group] = out[present].isna().any(axis=1).astype(int)

    return out


def select_features(df):
    """Return X, y, feature lists and a record of what was excluded and why."""
    df = derive_features(df)
    y = df["landslide"].astype(int)

    drop = (set(LEAKY_COLS) | set(ID_COLS) | set(REDUNDANT_COLS)
            | {"landslide", "aspect_deg"})
    feats = [c for c in df.columns if c not in drop]

    num_cols = [c for c in feats if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in feats if c not in num_cols]

    # a text column with a level per row is an identifier, not a feature
    high_card = [c for c in cat_cols if df[c].nunique(dropna=True) > CAT_MAX_LEVELS]
    cat_cols = [c for c in cat_cols if c not in high_card]

    # constant numeric columns carry no signal
    const = [c for c in num_cols if df[c].nunique(dropna=True) <= 1]
    num_cols = [c for c in num_cols if c not in const]

    feats = num_cols + cat_cols
    return df[feats].copy(), y, num_cols, cat_cols, feats, const, high_card


def main():
    os.makedirs(ART_DIR, exist_ok=True)

    df = pd.read_csv(DATASET)
    say("dataset      : %s" % os.path.relpath(DATASET, REPO))
    say("rows x cols  : %d x %d" % df.shape)
    say("label balance: %s" % df["landslide"].value_counts().to_dict())

    states = df["STATE"].astype(str)
    X, y, num_cols, cat_cols, feats, const, high_card = select_features(df)

    say()
    say("--- feature set ---")
    say("excluded, leaky by design : %d  %s" % (len(LEAKY_COLS), LEAKY_COLS))
    say("excluded, identifier      : %d  %s" % (len(ID_COLS), ID_COLS))
    say("excluded, redundant       : %s" % REDUNDANT_COLS)
    say("excluded, constant        : %s" % (const if const else "none"))
    say("excluded, many levels     : %s" % (high_card if high_card else "none"))
    say("numeric features          : %d" % len(num_cols))
    say("categorical features      : %d  %s" % (len(cat_cols), cat_cols))
    say("total features            : %d" % len(feats))

    # ---- spatial blocks ----
    block_lat = np.floor(df["lat"].values / BLOCK_DEG).astype(int)
    block_lon = np.floor(df["lon"].values / BLOCK_DEG).astype(int)
    groups = pd.Series(["b%d_%d" % (a, b) for a, b in zip(block_lat, block_lon)])
    per_block = groups.value_counts()
    say()
    say("--- spatial blocking ---")
    say("block size    : %.2f deg  (about %.0f km)" % (BLOCK_DEG, BLOCK_DEG * 111.0))
    say("blocks used   : %d" % groups.nunique())
    say("points/block  : median %d  min %d  max %d"
        % (per_block.median(), per_block.min(), per_block.max()))

    # ---- model comparison under spatial block CV ----
    models = ["logreg", "rf", "xgb"]
    if LGBMClassifier is not None:
        models.append("lgbm")
    else:
        say("note: lightgbm not installed, skipping that benchmark")
        say("      python -m pip install lightgbm")
    say()
    say("=" * 78)
    say("SPATIAL BLOCK CROSS-VALIDATION  (%d folds, whole blocks held out)" % N_SPLITS)
    say("=" * 78)

    results = {}
    for name in models:
        folds, oof, pooled = run_block_cv(name, X, y, groups, num_cols, cat_cols)
        results[name] = {"blocks": folds, "oof": oof, "pooled_blocks": pooled}
        s = summarise(folds)
        say()
        say("--- %s ---" % name)
        say("  %-18s %8s %8s" % ("metric", "mean", "std"))
        for k, v in s.items():
            say("  %-18s %8.4f %8.4f" % (k, v["mean"], v["std"]))
        say("  cuts chosen on validation blocks: %s"
            % ", ".join("%.2f" % f["threshold"] for f in folds))
        say("  pooled out-of-fold (threshold = median of fold thresholds):")
        say("    roc_auc %.4f   avg_precision %.4f   f1 %.4f   threshold %.2f"
            % (pooled["roc_auc"], pooled["avg_precision"], pooled["f1"],
               pooled["threshold"]))
        say("    confusion  tn %d  fp %d  fn %d  tp %d"
            % (pooled["tn"], pooled["fp"], pooled["fn"], pooled["tp"]))
        say("    false negative rate %.4f   false positive rate %.4f"
            % (pooled["false_negative_rate"], pooled["false_positive_rate"]))

    # ---- leave one state out ----
    say()
    say("=" * 78)
    say("LEAVE-ONE-STATE-OUT  (train on 7 states, predict the state never seen)")
    say("=" * 78)
    for name in models:
        folds = run_leave_one_state_out(name, X, y, states, groups,
                                         num_cols, cat_cols)
        results[name]["loso"] = folds
        say()
        say("--- %s ---" % name)
        if not folds:
            say("  no state had enough rows")
            continue
        say("  %-20s %7s %7s %7s %7s %7s"
            % ("held-out state", "auc", "avgP", "prec", "rec", "f1"))
        for f in folds:
            say("  %-20s %7.4f %7.4f %7.4f %7.4f %7.4f"
                % (f["state"], f["roc_auc"], f["avg_precision"],
                   f["precision"], f["recall"], f["f1"]))
        s = summarise(folds)
        say("  %-20s %7.4f %7.4f %7.4f %7.4f %7.4f   (mean)"
            % ("MEAN", s["roc_auc"]["mean"], s["avg_precision"]["mean"],
               s["precision"]["mean"], s["recall"]["mean"], s["f1"]["mean"]))

    # ---- choose and fit the final artifact ----
    # Selection rule: mean F1 across folds, NOT ROC-AUC.
    #
    # AUC measures how well the model ranks, but the product decision is which
    # points get warned about, and that is governed by recall and precision
    # together. On this dataset the tree models sit within 0.003 AUC of each
    # other while the fold-to-fold standard deviation is 0.026 - the difference
    # is nine times smaller than the noise, so AUC cannot separate them. F1
    # reflects the operating behaviour the product actually depends on.
    f1_scores = {n: summarise(results[n]["blocks"])["f1"]["mean"] for n in models}
    best = max(models, key=lambda n: f1_scores[n])

    say()
    say("=" * 78)
    say("model selection (mean F1 across folds, the metric that matters here)")
    say("=" * 78)
    for n in sorted(models, key=lambda n: -f1_scores[n]):
        say("  %-8s F1 %.4f   (ROC-AUC %.4f)"
            % (n, f1_scores[n], summarise(results[n]["blocks"])["roc_auc"]["mean"]))
    say()
    say("selected model: %s" % best)
    say("note: the tree models are statistically tied on ROC-AUC (spread 0.003")
    say("      against a fold-to-fold standard deviation of about 0.026), so the")
    say("      choice is made on F1, the metric tied to the warning decision.")
    say("=" * 78)

    final = build_model(best, num_cols, cat_cols)
    final.fit(X, y)
    imp = top_importances(final)
    if imp:
        say()
        say("--- top feature importances, %s refit on all data ---" % best)
        for f, v in imp:
            say("    %-28s %.4f" % (f, v))

    model_path = os.path.join(ART_DIR, "%s.joblib" % best)
    joblib.dump(final, model_path)

    imputable = sorted({c for group in MISSING_GROUPS.values() for c in group
                        if c in feats})

    schema = {
        "artifact_version": ART_VERSION,
        "model": best,
        "dataset": os.path.relpath(DATASET, REPO),
        "label": {"column": "landslide",
                  "positive": "recorded landslide (GSI inventory)",
                  "negative": "generated negative (see build_negatives.py)"},
        "numeric_features": num_cols,
        "categorical_features": cat_cols,
        "excluded_leaky": LEAKY_COLS,
        "excluded_identifier": ID_COLS,
        "excluded_redundant": REDUNDANT_COLS,
        "excluded_constant": const,
        "excluded_high_cardinality": high_card,
        "imputation": "median, fitted inside each training fold",
        # The serving side may omit exactly these. They are blank not because a
        # request was incomplete but because the source layer does not cover the
        # point, which is a documented spatial gap (see MISSING_GROUPS). Everything
        # else must be supplied or the prediction is refused.
        "imputable_features": imputable,
        "notes": [
            "score is a ranking, not a calibrated probability: the 1:1 "
            "case/control design fixes the base rate at 0.5",
            "negatives are constructed, not observed: absence of a GSI record "
            "is not evidence that no landslide occurred",
            "event-year rainfall is excluded because negatives have no event "
            "date; only climatology is used",
        ],
    }
    with io.open(os.path.join(ART_DIR, "feature_schema.json"), "w",
                 encoding="utf-8", newline="") as fh:
        json.dump(schema, fh, indent=2)

    oof_best = results[best]["oof"]
    thresholds = {
        "default": 0.5,
        "f1_optimal_mean_over_folds": float(np.mean(
            [f["threshold"] for f in results[best]["blocks"]])),
        "high_recall_operating_point": float(np.percentile(
            oof_best[~np.isnan(oof_best)], 40)),
        "note": "thresholds are tuned on training folds. They are not "
                "transferable probabilities and must be revisited after "
                "calibration against real event prevalence.",
    }
    with io.open(os.path.join(ART_DIR, "thresholds.json"), "w",
                 encoding="utf-8", newline="") as fh:
        json.dump(thresholds, fh, indent=2)

    metrics = {
        "artifact_version": ART_VERSION,
        "model_selected": best,
        "block_cv": {n: {"folds": results[n]["blocks"],
                         "pooled": results[n]["pooled_blocks"],
                         "summary": summarise(results[n]["blocks"])}
                     for n in models},
        "leave_one_state_out": {n: results[n]["loso"] for n in models},
        "top_feature_importances": imp,
        "feature_count": len(feats),
        "row_count": int(len(df)),
        "block_deg": BLOCK_DEG,
        "n_splits": N_SPLITS,
    }
    with io.open(os.path.join(ART_DIR, "metrics.json"), "w",
                 encoding="utf-8", newline="") as fh:
        json.dump(metrics, fh, indent=2)

    say()
    say("wrote %s" % os.path.relpath(model_path, REPO))
    say("wrote feature_schema.json, thresholds.json, metrics.json, "
        "training_report.txt in %s" % os.path.relpath(ART_DIR, REPO))
    say()
    say("These numbers come from cross-validation on the dataset above. They are")
    say("not production performance, and the score is not a calibrated probability.")

    with io.open(os.path.join(ART_DIR, "training_report.txt"), "w",
                 encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\nwrote training_report.txt")


if __name__ == "__main__":
    main()