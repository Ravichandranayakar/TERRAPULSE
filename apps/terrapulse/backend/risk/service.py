from collections.abc import Iterable

from .predictor import DevelopmentRiskPredictor, RiskPredictor
from .schemas import RiskFeatureInput, RiskPrediction, TrainedRiskFeatureInput
from .trained_predictor import (ArtifactUnavailable, TrainedMLRiskPredictor,
                                model_dir)


# The rule-based predictor stays the default for the meteorological payload the
# simulator and the map already send. The trained model needs extracted
# geospatial features that payload does not carry, so it is reached through its
# own functions instead of silently replacing this one: swapping the default
# would score every existing cell with a model missing most of its inputs.
_PREDICTOR: RiskPredictor = DevelopmentRiskPredictor()

_trained: TrainedMLRiskPredictor | None = None


def predict_development_risk(features: RiskFeatureInput) -> RiskPrediction:
    return _PREDICTOR.predict(features)


def predict_development_risk_batch(features: Iterable[RiskFeatureInput]) -> list[RiskPrediction]:
    return [_PREDICTOR.predict(item) for item in features]


def trained_predictor() -> TrainedMLRiskPredictor:
    """The trained model, loaded once and cached.

    Raises ArtifactUnavailable when the artifact is missing, so callers report a
    clear state instead of a confusing 500.
    """
    global _trained
    if _trained is None:
        _trained = TrainedMLRiskPredictor()
    return _trained


def trained_predictor_status() -> dict:
    """Whether the trained artifact is loadable. Reports a state, never a score."""
    try:
        predictor = trained_predictor()
    except ArtifactUnavailable as error:
        return {
            "available": False,
            "artifact_dir": model_dir(),
            "error": str(error),
        }

    return {
        "available": True,
        "artifact_dir": model_dir(),
        "model": predictor.name,
        "predictor_type": predictor.predictor_type,
        "alert_cut": predictor.alert_cut,
        "feature_count": len(predictor.features),
        "note": "risk_score is a ranking, not a calibrated probability",
    }


def predict_trained_risk(features: TrainedRiskFeatureInput) -> RiskPrediction:
    return trained_predictor().predict(features)


def predict_trained_risk_batch(features: Iterable[TrainedRiskFeatureInput]) -> list[RiskPrediction]:
    predictor = trained_predictor()
    return [predictor.predict(item) for item in features]