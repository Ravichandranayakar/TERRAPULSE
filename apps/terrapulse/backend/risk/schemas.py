from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskFeatureInput(BaseModel):
    """Feature payload shared by development and future trained predictors."""

    model_config = ConfigDict(extra="forbid")

    cell_id: str = Field(min_length=1, max_length=120)
    lat: float | None = None
    lon: float | None = None
    rainfall_1h: float | None = Field(default=None, ge=0)
    rainfall_3h: float | None = Field(default=None, ge=0)
    rainfall_6h: float | None = Field(default=None, ge=0)
    rainfall_24h: float | None = Field(default=None, ge=0)
    antecedent_rainfall: float | None = Field(default=None, ge=0)
    soil_moisture: float | None = Field(default=None, ge=0, le=1)
    elevation: float | None = Field(default=None, ge=0)
    slope: float | None = Field(default=None, ge=0, le=90)
    aspect: float | None = Field(default=None, ge=0, le=360)
    historical_susceptibility: float | None = Field(default=None, ge=0, le=1)


class RiskBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cells: list[RiskFeatureInput] = Field(min_length=1, max_length=500)


class RiskPrediction(BaseModel):
    """Standardized response consumed by the simulator and map state."""

    cell_id: str
    risk_score: float = Field(ge=0, le=100)
    risk_class: str
    risk_level: str
    drivers: list[str]
    features: dict[str, float | None]
    normalized_features: dict[str, float]
    missing_features: list[str]
    contributing_factors: list[dict[str, Any]]
    warning_ready: bool
    predictor: str = "development"
    predictor_type: str = "rule_based"
