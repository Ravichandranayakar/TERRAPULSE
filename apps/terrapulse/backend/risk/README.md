# Risk Prediction Contract

This package contains the replaceable risk-prediction boundary used by the
Storm Simulator. Two predictors implement it.

## Current implementation

### DevelopmentRiskPredictor (default)

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

### TrainedMLRiskPredictor

Wraps the trained susceptibility model - the LightGBM model validated in
`model_evaluation.md` and resolved through `models/registry.json`. It satisfies the
same `RiskPredictor` protocol and returns the same `RiskPrediction` shape.

**It does not take the same input.** The trained model consumes the extracted
terrain, rainfall-climatology, soil, land-cover, distance and Bhuvan geology
features named in the artifact's `feature_schema.json`, which is what
`scripts/extract_*.py` and `scripts/fetch_cell_bhuvan.py` produce for a point. It
never pads missing features with defaults: a payload that cannot supply the full
vector is rejected with 422, because substituting medians for most of the vector
would return a confident-looking score that reflects almost nothing. The one
exception is the columns the schema lists under `imputable_features`, which are
blank because the source layer does not cover the point. Coordinates are
provenance only - the model does not accept raw coordinates.

The vector must also be **post-derivation**. The schema names four columns the
extraction step does not write directly (`aspect_sin`, `aspect_cos` and the
missingness flags), so the feature dict must be built the way
`scripts/predict_landslide.py` builds it before scoring. A caller that passes
raw extracted columns gets a 422 listing exactly what is absent.

The artifact directory is resolved through `<repo>/models/registry.json`, so the
version marked active is the one served; set `TERRAPULSE_MODEL_DIR` to override it
for a local experiment. The backend deploys as its own Docker context, so the
artifacts must be copied or mounted at deploy time. When they are absent the API
returns 503 rather than falling back to a different model's score under the same
field names.

Two limits apply to every trained score:

- it is a **ranking, not a probability**. The model was trained on a 1:1
  case/control sample, so its base rate is 0.5, which is not the real event rate.
- `contributing_factors` reports **global feature importances**, not per-row
  attribution. A per-row explanation needs SHAP or similar and is not computed here.

## API

Rule-based, meteorological payload:

- `POST /api/risk/predict` accepts one `RiskFeatureInput`.
- `POST /api/risk/predict-batch` accepts up to 500 spatial feature payloads.

Trained model, extracted feature payload:

- `GET /api/risk/model-status` reports whether the artifact loads. It returns a
  state, never a score, so it is safe to call before wiring anything up.
- `POST /api/risk/predict-trained` accepts one `TrainedRiskFeatureInput`.
- `POST /api/risk/predict-trained-batch` accepts up to 500 of them.

Both families return the same standardized result shape: score, risk class,
drivers, raw feature values, normalized values, missing-feature metadata,
compatible `contributing_factors`, and predictor metadata. `warning_ready` means
only that the score reached the current alert cut; it is not a claim that a
landslide will occur.

The `predictor` and `predictor_type` fields identify which model produced a
score (`development` / `rule_based`, or `rf` /
`trained_susceptibility_classifier`), so a caller can always tell them apart.

## Map cells are scored by the trained model

The map and the live cycle no longer depend on a caller assembling a feature vector.
`scripts/extract_cell_features.py` runs the same extraction logic at the monitoring-
cell centroids and writes `apps/terrapulse/backend/data/ner_cell_features.json`. The
live cycle in `live_pipeline.py` merges those static features with live rainfall and
soil moisture and calls `TrainedMLRiskPredictor` for every cell. `GET /api/live/risk`
returns the result.

The extractor records a fingerprint of the five source datasets it read. Stage 03 of
`pipeline.py` compares that fingerprint against the files on disk and reruns the
extractor when one of them is republished, so the stored values cannot silently drift
from the data they describe.

The Storm Simulator still sends the meteorological payload and still runs on the
development predictor. Moving it onto the trained model means assembling the same
feature vector for the scenario cells.

## Future migration

Keep the API response contract stable so the simulator, shared map state,
warning UI, and 2D/3D map do not need to change.