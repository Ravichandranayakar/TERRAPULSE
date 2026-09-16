"""Trained landslide susceptibility model behind the RiskPredictor protocol.

Serves the LightGBM model validated in model_evaluation.md and written to
models/landslide_v0.4 by scripts/train_landslide_model.py. It reads terrain,
rainfall climatology, soil, land cover, distance, and Bhuvan geomorphology and
lineament features.

Input
  This predictor does NOT take the meteorological payload that
  DevelopmentRiskPredictor accepts. The trained model consumes the extracted
  terrain, rainfall-climatology, soil, land-cover, distance and Bhuvan
  geology features named in the artifact's feature_schema.json - the output of
  the scripts/extract_*.py pipeline (plus scripts/fetch_cell_bhuvan.py) for a
  point. A payload that cannot supply them is rejected rather than padded with
  defaults: substituting medians for most of the feature vector would produce a
  confident-looking score that reflects almost nothing.

  The one exception is the columns listed in the artifact's
  imputable_features: those are blank because the source layer does not cover
  the point, which is a documented spatial gap the training folds imputed for.
  They may be absent from a payload. Everything else must be supplied.

Output
  risk_score is the model score scaled to 0-100 so it satisfies the shared
  response contract. It is a ranking, not a probability. The model was trained
  on a 1:1 case/control sample, so its base rate is 0.5, which is not the real
  event rate.

Explanations
  contributing_factors reports the model's GLOBAL feature importances for the
  features actually supplied, with the supplied raw values alongside them. It is
  not a per-prediction attribution; a per-row explanation needs SHAP or similar,
  which this module deliberately does not compute.

Where the artifact lives
  Default is <repo>/models/landslide_v0.4, overridden by TERRAPULSE_MODEL_DIR.
  The backend deploys as its own Docker context, so the artifact must be copied
  or mounted at deploy time. When it is absent the API returns 503 and never
  silently falls back to the rule-based predictor, because a fallback would
  return a different model's score under the same field names.
"""

import io
import json
import os
from dataclasses import dataclass
from typing import Any

import joblib
import pandas as pd

from .schemas import RiskPrediction, TrainedRiskFeatureInput


MODEL_DIR_ENV = "TERRAPULSE_MODEL_DIR"

# <this file>/../../../../ = repository root
DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir, os.pardir, os.pardir, os.pardir,
    "models", "landslide_v0.4")

# Bands that place a score into the risk-class vocabulary the existing UI
# already renders. Anchored on operating points measured on held-out spatial
# blocks for THIS artifact, not invented:
#   >= 0.69  precision 0.75  three of every four warnings are recorded landslides
#   >= 0.28  recall    0.80  catches four of every five recorded landslides
#   >= 0.10  recall    0.95  catches nineteen of every twenty
# Lowering a band trades false alarms for missed landslides; the full table is
# in scripts/model_operating_points.py output. These are operational bands, NOT
# validated severity classes. See model_evaluation.md section 5.
RISK_BANDS = ((0.69, "CRITICAL"), (0.28, "HIGH"), (0.10, "MODERATE"), (0.0, "LOW"))

TOP_FACTORS = 5


class ArtifactUnavailable(RuntimeError):
    """The trained artifact is missing or unreadable."""


@dataclass(frozen=True)
class LoadedArtifact:
    model: Any
    schema: dict
    thresholds: dict
    importances: dict


def _registry_active_dir() -> str | None:
    """Directory of the version the feedback loop has promoted to active.

    Without this, a retrained model would be promoted in the registry and then
    never served, because the predictor would keep reading the shipped folder.
    """
    registry_path = os.path.join(os.path.dirname(DEFAULT_MODEL_DIR), "registry.json")
    if not os.path.exists(registry_path):
        return None
    try:
        with io.open(registry_path, encoding="utf-8") as handle:
            registry = json.load(handle)
    except (ValueError, OSError):
        return None

    active = registry.get("active")
    if not active:
        return None

    for version in registry.get("versions", []):
        if version.get("version") == active:
            directory = version.get("directory")
            if directory and os.path.exists(os.path.join(directory, "feature_schema.json")):
                return os.path.abspath(directory)
            return None
    return None


def model_dir() -> str:
    """Directory holding the model artifact.

    Precedence: explicit environment override, then the registry's active
    version, then the shipped default.
    """
    override = os.environ.get(MODEL_DIR_ENV)
    if override:
        return os.path.abspath(override)
    return _registry_active_dir() or os.path.abspath(DEFAULT_MODEL_DIR)


def _read_json(path: str) -> dict:
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_artifact(directory: str | None = None) -> LoadedArtifact:
    """Load the saved model with its schema, thresholds and importances."""
    directory = directory or model_dir()
    schema_path = os.path.join(directory, "feature_schema.json")
    if not os.path.exists(schema_path):
        raise ArtifactUnavailable(
            "no feature_schema.json in %s. Run scripts/train_landslide_model.py, "
            "or point %s at the directory that holds the artifact."
            % (directory, MODEL_DIR_ENV))

    schema = _read_json(schema_path)

    thresholds_path = os.path.join(directory, "thresholds.json")
    thresholds = _read_json(thresholds_path) if os.path.exists(thresholds_path) else {}

    importances: dict[str, float] = {}
    metrics_path = os.path.join(directory, "metrics.json")
    if os.path.exists(metrics_path):
        recorded = _read_json(metrics_path).get("top_feature_importances") or []
        if isinstance(recorded, dict):
            importances = {str(k): float(v) for k, v in recorded.items()}
        else:
            importances = {str(name): float(value) for name, value in recorded}

    model_path = os.path.join(directory, "%s.joblib" % schema["model"])
    if not os.path.exists(model_path):
        raise ArtifactUnavailable("no model file at %s" % model_path)

    try:
        model = joblib.load(model_path)
    except Exception as error:  # surfaced as a clear 503 rather than a 500
        raise ArtifactUnavailable("could not load %s: %s" % (model_path, error))

    return LoadedArtifact(model=model, schema=schema, thresholds=thresholds,
                          importances=importances)


def required_features(schema: dict) -> list:
    """Feature columns the artifact expects, in schema order."""
    return list(schema.get("numeric_features", [])) + list(schema.get("categorical_features", []))


def _plain_name(name: str) -> str:
    """Strip the pipeline prefix the training report records (num__ / cat__)."""
    return name.split("__", 1)[-1] if "__" in name else name


def _risk_class(score: float) -> str:
    for lower, label in RISK_BANDS:
        if score >= lower:
            return label
    return RISK_BANDS[-1][1]


class TrainedMLRiskPredictor:
    """Protocol-compatible wrapper around the trained susceptibility model."""

    def __init__(self, artifact: LoadedArtifact | None = None) -> None:
        self._artifact = artifact if artifact is not None else load_artifact()
        self.name = str(self._artifact.schema.get("model", "trained"))
        self.predictor_type = "trained_susceptibility_classifier"
        self.features = required_features(self._artifact.schema)
        self.alert_cut = float(
            self._artifact.thresholds.get("f1_optimal_mean_over_folds", 0.5))

    def predict(self, features: TrainedRiskFeatureInput) -> RiskPrediction:
        supplied = dict(features.features)
        # Absent is not the same as unsupplied. The imputable columns are blank
        # for a documented spatial reason and were imputed during training, so a
        # missing one is expected; every other feature is required.
        imputable = set(self._artifact.schema.get("imputable_features") or [])
        missing = [name for name in self.features
                   if supplied.get(name) is None and name not in imputable]
        if missing:
            raise ValueError(
                "the trained predictor needs %d feature column(s) and %d are "
                "missing: %s. These come from scripts/extract_*.py for a point; "
                "this predictor will not substitute defaults for them."
                % (len(self.features), len(missing),
                   ", ".join(sorted(missing)[:12])))

        row = pd.DataFrame([{name: supplied[name] for name in self.features}])
        score = float(self._artifact.model.predict_proba(row)[:, 1][0])
        risk_class = _risk_class(score)

        factors = []
        ordered = sorted(self._artifact.importances.items(),
                         key=lambda item: item[1], reverse=True)
        for recorded_name, importance in ordered[:TOP_FACTORS]:
            name = _plain_name(recorded_name)
            if name not in supplied:
                continue
            factors.append({
                "factor": name,
                "value": round(importance * 100.0, 2),
                "unit": "%",
                "raw": supplied[name],
                "raw_unit": "model feature",
                "weight": round(float(importance), 4),
                "basis": "global_model_importance",
            })

        return RiskPrediction(
            cell_id=features.cell_id,
            risk_score=round(score * 100.0, 1),
            risk_class=risk_class,
            risk_level=risk_class.lower(),
            drivers=[factor["factor"] for factor in factors],
            features={name: supplied.get(name) for name in self.features},
            # The trained model does not use the 0-1 rescaling that the
            # development predictor applies, so there is nothing honest to put
            # here. Left empty rather than filled with a different scale.
            normalized_features={},
            missing_features=[],
            contributing_factors=factors,
            warning_ready=score >= self.alert_cut,
            predictor=self.name,
            predictor_type=self.predictor_type,
        )