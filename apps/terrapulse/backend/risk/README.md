# Risk Prediction Contract

This package contains the replaceable risk-prediction boundary used by the
Storm Simulator.

## Current implementation

`DevelopmentRiskPredictor` is a deterministic rule-based heuristic for
development demonstrations. It is not trained, calibrated, scientifically
validated, or suitable for production decisions.

The predictor normalizes rainfall, soil moisture, terrain, elevation, and
historical susceptibility inputs, then calculates an internal 0-100 score from
configurable placeholder weights in `predictor.py`. Aspect is accepted and
normalized for contract compatibility, but is currently retained without a
heuristic contribution because its effect requires validated domain data.

Missing values are recorded in `missing_features` and receive explicit neutral
development defaults from `FEATURE_DEFAULTS`; they are not presented as real
measurements.

## API

- `POST /api/risk/predict` accepts one `RiskFeatureInput`.
- `POST /api/risk/predict-batch` accepts up to 500 spatial feature payloads.

Both return the same standardized result shape: score, risk class, drivers,
raw feature values, normalized values, missing-feature metadata, compatible
`contributing_factors`, and predictor metadata. `warning_ready` means only that
the development score reached the current UI warning band; it is not a claim
that a landslide will occur.

## Future migration

Replace the `_PREDICTOR` implementation in `service.py` with a validated
predictor that satisfies the `RiskPredictor` protocol. Keep the API response
contract stable so the simulator, shared map state, warning UI, and 2D/3D map
do not need to change.
