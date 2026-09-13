from dataclasses import dataclass
from typing import Protocol

from .schemas import RiskFeatureInput, RiskPrediction


FEATURE_DEFAULTS: dict[str, float] = {
    "rainfall_1h": 0.0,
    "rainfall_3h": 0.0,
    "rainfall_6h": 0.0,
    "rainfall_24h": 0.0,
    "antecedent_rainfall": 0.0,
    "soil_moisture": 0.5,
    "elevation": 0.0,
    "slope": 0.0,
    "aspect": 180.0,
    "historical_susceptibility": 0.5,
}

NORMALIZATION_LIMITS: dict[str, float] = {
    "rainfall_1h": 100.0,
    "rainfall_3h": 180.0,
    "rainfall_6h": 280.0,
    "rainfall_24h": 400.0,
    "antecedent_rainfall": 500.0,
    "elevation": 4000.0,
    "slope": 60.0,
}

DEVELOPMENT_WEIGHTS: dict[str, float] = {
    "rainfall_1h": 0.08,
    "rainfall_3h": 0.10,
    "rainfall_6h": 0.10,
    "rainfall_24h": 0.12,
    "antecedent_rainfall": 0.18,
    "soil_moisture": 0.12,
    "slope": 0.15,
    "elevation": 0.05,
    "historical_susceptibility": 0.10,
}

DRIVER_LABELS: dict[str, tuple[str, str, str]] = {
    "rainfall_1h": ("Recent Rainfall (1h)", "mm", "Recent rainfall contribution"),
    "rainfall_3h": ("3-Hour Accumulated Rainfall", "mm", "Short-duration rainfall contribution"),
    "rainfall_6h": ("6-Hour Accumulated Rainfall", "mm", "Accumulated rainfall contribution"),
    "rainfall_24h": ("Recent Rainfall (24h)", "mm", "Recent rainfall contribution"),
    "antecedent_rainfall": ("Antecedent Rainfall (7-Day)", "mm", "Elevated antecedent rainfall contribution"),
    "soil_moisture": ("Soil Moisture", "index", "Elevated soil-moisture contribution"),
    "slope": ("Slope Angle", "deg", "Steep slope contribution"),
    "elevation": ("Elevation", "m", "Elevation contribution"),
    "historical_susceptibility": ("Geological Susceptibility", "index", "High baseline susceptibility contribution"),
}


@dataclass(frozen=True)
class PreparedFeatures:
    raw: dict[str, float | None]
    normalized: dict[str, float]
    missing: list[str]


class RiskPredictor(Protocol):
    name: str
    predictor_type: str

    def predict(self, features: RiskFeatureInput) -> RiskPrediction:
        ...


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def prepare_features(features: RiskFeatureInput) -> PreparedFeatures:
    raw: dict[str, float | None] = {}
    normalized: dict[str, float] = {}
    missing: list[str] = []

    for name, default in FEATURE_DEFAULTS.items():
        value = getattr(features, name)
        if value is None:
            missing.append(name)
            value = default
        raw[name] = value

        if name in ("soil_moisture", "historical_susceptibility"):
            normalized[name] = _clamp(value)
        elif name == "aspect":
            normalized[name] = _clamp(value / 360.0)
        else:
            normalized[name] = _clamp(value / NORMALIZATION_LIMITS[name])

    return PreparedFeatures(raw=raw, normalized=normalized, missing=missing)


class DevelopmentRiskPredictor:
    """Deterministic, transparent heuristic used until validated ML is ready."""

    name = "development"
    predictor_type = "rule_based"

    def predict(self, features: RiskFeatureInput) -> RiskPrediction:
        prepared = prepare_features(features)
        contributions = {
            name: prepared.normalized[name] * weight
            for name, weight in DEVELOPMENT_WEIGHTS.items()
        }
        score = round(_clamp(sum(contributions.values())) * 100.0, 1)
        risk_class = self._risk_class(score)

        material = sorted(
            ((name, value * 100.0) for name, value in contributions.items() if value * 100.0 >= 5.0),
            key=lambda item: item[1],
            reverse=True,
        )
        drivers = [DRIVER_LABELS[name][2] for name, _ in material[:5]]
        if not drivers:
            drivers = ["No material development contribution exceeded the reporting threshold"]

        contributing_factors = []
        for name, contribution in material:
            label, unit, _ = DRIVER_LABELS[name]
            contributing_factors.append({
                "factor": label,
                "value": round(contribution, 1),
                "unit": "%",
                "raw": round(prepared.raw[name], 3),
                "raw_unit": unit,
                "weight": DEVELOPMENT_WEIGHTS[name],
            })

        return RiskPrediction(
            cell_id=features.cell_id,
            risk_score=score,
            risk_class=risk_class,
            risk_level=risk_class.lower(),
            drivers=drivers,
            features=prepared.raw,
            normalized_features={name: round(value, 4) for name, value in prepared.normalized.items()},
            missing_features=prepared.missing,
            contributing_factors=contributing_factors,
            warning_ready=risk_class in {"HIGH", "CRITICAL"},
            predictor=self.name,
            predictor_type=self.predictor_type,
        )

    @staticmethod
    def _risk_class(score: float) -> str:
        if score >= 75.0:
            return "CRITICAL"
        if score >= 55.0:
            return "HIGH"
        if score >= 35.0:
            return "MODERATE"
        return "LOW"
