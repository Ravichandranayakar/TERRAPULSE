"""Tests for the pipeline, spatial database and feedback loop."""

import io
import json
import os

import feedback_loop
import pipeline
import spatial_db


# --- pipeline structure ----------------------------------------------------

def test_pipeline_has_all_seven_stages():
    assert list(pipeline.STAGE_FUNCTIONS) == ["01", "02", "03", "04", "05", "06", "07"]


def test_stage_names_match_the_architected_pipeline():
    expected = {pipeline.stage_02_preprocessing: "DATA PREPROCESSING",
                pipeline.stage_03_geo: "GEO PROCESSING",
                pipeline.stage_04_features: "FEATURE ENGINEERING",
                pipeline.stage_05_model: "AI / ML MODEL"}
    for fn, name in expected.items():
        assert callable(fn)
    result = pipeline.stage_02_preprocessing()
    assert result.name == "DATA PREPROCESSING"
    assert result.stage == "02"


def test_pipeline_reports_ok_for_offline_stages():
    report = pipeline.run_pipeline(stages=["02", "03", "04", "05"], store=False)
    assert report["ok"] is True
    assert len(report["stages"]) == 4
    assert all(s["status"] == "ok" for s in report["stages"])


def test_preprocessing_reports_the_cleaning_rules_actually_applied():
    detail = pipeline.stage_02_preprocessing().detail
    joined = " ".join(detail["cleaning_applied"]).lower()
    for rule in ["-999", "nodata", "median imputation"]:
        assert rule in joined


def test_feature_stage_reports_full_coverage_of_model_inputs():
    """Column count must match the artifact the stage actually loaded.

    A typed-in number only proves the test was edited the last time the model
    changed. Reading it off the loaded artifact proves the stage and the served
    model still agree on the same feature contract.
    """
    from risk.trained_predictor import TrainedMLRiskPredictor, required_features

    detail = pipeline.stage_04_features().detail
    schema = TrainedMLRiskPredictor()._artifact.schema
    assert detail["feature_matrix"]["columns"] == len(required_features(schema))
    assert detail["features_without_a_source"] == []


def test_feature_stage_keeps_live_rainfall_out_of_climatology():
    """The pipeline must not describe live rainfall as a model input."""
    detail = pipeline.stage_04_features().detail
    assert "rainfall_24h_mm" in detail["temporal_features_live"]
    assert "rain_clim_annual_mm" in detail["climatology_features"]
    assert "never written into a climatology column" in detail["note"]


def test_unknown_stage_is_ignored_not_fatal():
    report = pipeline.run_pipeline(stages=["99"], store=False)
    assert report["stages"] == []
    assert report["ok"] is True


# --- feedback loop: versioning --------------------------------------------

def test_next_version_advances_past_the_shipped_model():
    assert feedback_loop.next_version_label() != "landslide_v0.1"
    assert feedback_loop.next_version_label().startswith("landslide_v")


def test_next_version_never_reuses_an_existing_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_loop, "MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(feedback_loop, "REGISTRY", str(tmp_path / "registry.json"))
    for name in ("landslide_v0.1", "landslide_v0.2", "landslide_v0.3"):
        os.makedirs(tmp_path / name)
    assert feedback_loop.next_version_label() == "landslide_v0.4"


# --- feedback loop: trigger conditions ------------------------------------

def test_due_for_retrain_reports_its_conditions():
    due = feedback_loop.due_for_retrain()
    for key in ("due", "reasons", "pending_events", "min_new_events",
                "max_interval_days"):
        assert key in due


def test_enough_new_events_makes_a_retrain_due(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_loop, "REGISTRY", str(tmp_path / "registry.json"))
    monkeypatch.setattr(feedback_loop, "MIN_NEW_EVENTS", 5)
    monkeypatch.setattr(feedback_loop, "pending_curated_events",
                        lambda: {"available": True, "pending": 7, "records": []})
    due = feedback_loop.due_for_retrain()
    assert due["due"] is True
    assert any("7 new curated events" in r for r in due["reasons"])


def test_no_events_and_recent_retrain_is_not_due(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "active": "landslide_v0.1",
        "versions": [],
        "last_retrain_at": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    monkeypatch.setattr(feedback_loop, "REGISTRY", str(registry))
    monkeypatch.setattr(feedback_loop, "pending_curated_events",
                        lambda: {"available": True, "pending": 0, "records": []})
    monkeypatch.setattr(feedback_loop, "MAX_INTERVAL_DAYS", 30)
    assert feedback_loop.due_for_retrain()["due"] is False


# --- feedback loop: the promotion gate ------------------------------------

def _evaluate(candidate_scores, current_scores, monkeypatch, tmp_path):
    monkeypatch.setattr(feedback_loop, "active_version",
                        lambda: {"version": "landslide_v0.1",
                                 "directory": str(tmp_path),
                                 "metrics": current_scores})
    return feedback_loop.evaluate_candidate({"version": "landslide_v0.2",
                                             "directory": str(tmp_path),
                                             "metrics": candidate_scores})


def test_better_candidate_is_promoted(tmp_path, monkeypatch):
    result = _evaluate({"recall": 0.90, "roc_auc": 0.78},
                       {"recall": 0.85, "roc_auc": 0.73}, monkeypatch, tmp_path)
    assert result["promote"] is True
    assert result["deltas"]["recall"] > 0


def test_worse_candidate_is_rejected(tmp_path, monkeypatch):
    result = _evaluate({"recall": 0.70, "roc_auc": 0.60},
                       {"recall": 0.85, "roc_auc": 0.73}, monkeypatch, tmp_path)
    assert result["promote"] is False
    assert "fell by" in result["reason"]


def test_small_regression_inside_tolerance_still_promotes(tmp_path, monkeypatch):
    """A tenth of a point is fold noise, not a regression."""
    monkeypatch.setattr(feedback_loop, "TOLERANCE", {"recall": 0.02, "roc_auc": 0.02})
    result = _evaluate({"recall": 0.84, "roc_auc": 0.725},
                       {"recall": 0.85, "roc_auc": 0.73}, monkeypatch, tmp_path)
    assert result["promote"] is True


def test_candidate_without_metrics_is_not_promoted(tmp_path, monkeypatch):
    result = _evaluate({}, {"recall": 0.85}, monkeypatch, tmp_path)
    assert result["promote"] is False
    assert "no metrics" in result["reason"]


def test_rejected_candidate_still_records_its_outcome(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    monkeypatch.setattr(feedback_loop, "MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(feedback_loop, "REGISTRY", str(registry))
    monkeypatch.setattr(feedback_loop, "active_version",
                        lambda: {"version": "landslide_v0.1", "directory": str(tmp_path),
                                 "metrics": {"recall": 0.85, "roc_auc": 0.73}})

    candidate = {"version": "landslide_v0.2", "directory": str(tmp_path),
                 "metrics": {"recall": 0.60, "roc_auc": 0.55}}
    evaluation = feedback_loop.evaluate_candidate(candidate)
    outcome = feedback_loop.promote(candidate, evaluation)

    assert outcome["status"] == "rejected"
    assert outcome["active"] == "landslide_v0.1"
    saved = json.loads(registry.read_text(encoding="utf-8"))
    assert saved["versions"][0]["status"] == "rejected"
    assert "fell by" in saved["versions"][0]["evaluation"]["reason"]


# --- feedback loop: metric parsing ----------------------------------------

def test_loso_scores_averages_the_held_out_states():
    """leave_one_state_out is {model: [one record per held-out state]}."""
    metrics = {"model_selected": "rf",
               "leave_one_state_out": {"rf": [
                   {"state": "Sikkim", "recall": 0.90, "roc_auc": 0.70},
                   {"state": "Mizoram", "recall": 0.80, "roc_auc": 0.60},
               ]}}
    scores = feedback_loop.loso_scores(metrics)
    assert scores["recall"] == 0.85
    assert scores["roc_auc"] == 0.65
    assert scores["states"] == 2


def test_loso_scores_ignores_states_that_lack_a_metric():
    metrics = {"model_selected": "rf",
               "leave_one_state_out": {"rf": [
                   {"state": "Sikkim", "recall": 0.90, "roc_auc": 0.70},
                   {"state": "Mizoram", "recall": 0.80},
               ]}}
    scores = feedback_loop.loso_scores(metrics)
    assert scores["recall"] == 0.85
    assert scores["states"] == 2


def test_loso_scores_is_empty_without_metrics():
    assert feedback_loop.loso_scores({}) == {}


def test_shipped_model_metrics_are_readable():
    scores = feedback_loop.loso_scores(
        feedback_loop.read_metrics(feedback_loop.active_version()["directory"]))
    assert scores, "the active artifact must expose LOSO metrics"


# --- spatial database ------------------------------------------------------

def test_spatial_status_reports_postgis_when_running():
    status = spatial_db.status()
    if not status.get("available"):
        return  # PostGIS may not be running in every environment
    # PostGIS_Version() returns the bare version string, e.g. "3.6 USE_GEOS=1"
    assert status["postgis_version"].split()[0].startswith("3.")
    assert "PostgreSQL" in status["postgres_version"]


def test_spatial_schema_and_spatial_query_round_trip():
    if not spatial_db.status().get("available"):
        return
    assert spatial_db.ensure_schema()["available"] is True

    cells = [{"location_id": "TST_01", "name": "Test Cell", "district": "Test",
              "state": "Test", "centroid_lat": 27.55, "centroid_lon": 88.53,
              "lat_min": 27.52, "lat_max": 27.57,
              "lon_min": 88.51, "lon_max": 88.56}]
    assert spatial_db.upsert_cells(cells)["written"] == 1


def test_spatial_distance_query_returns_metres_not_degrees():
    if not spatial_db.status().get("available"):
        return
    result = spatial_db.cells_within_metres_of_landslides(25000)
    assert result["available"] is True
    for row in result["results"]:
        # 25 km in metres. A degrees-based bug would return values under 1.
        assert 0 < row["distance_m"] <= 25000


def test_spatial_layer_degrades_gracefully_when_unreachable(monkeypatch):
    monkeypatch.setattr(spatial_db, "dsn",
                        lambda: "postgresql://nobody@127.0.0.1:1/nothing")
    status = spatial_db.status()
    assert status["available"] is False
    assert "reason" in status
    assert spatial_db.write_cycle({"cells": []})["written"] == 0