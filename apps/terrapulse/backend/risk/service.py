from collections.abc import Iterable

from .predictor import DevelopmentRiskPredictor, RiskPredictor
from .schemas import RiskFeatureInput, RiskPrediction


_PREDICTOR: RiskPredictor = DevelopmentRiskPredictor()


def predict_development_risk(features: RiskFeatureInput) -> RiskPrediction:
    return _PREDICTOR.predict(features)


def predict_development_risk_batch(features: Iterable[RiskFeatureInput]) -> list[RiskPrediction]:
    return [_PREDICTOR.predict(item) for item in features]
