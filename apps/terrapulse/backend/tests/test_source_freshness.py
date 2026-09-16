"""The per-cell feature values are computed from the source files, so they must
be rebuilt when one of those files is republished.

These tests cover the detector that decides whether a rebuild is due, and the
artifact's own record of which release of each source it read.
"""

import copy
import io
import json
import os
import sys

import pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(BACKEND, os.pardir, os.pardir, os.pardir))
SCRIPTS = os.path.join(REPO, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import pytest  # noqa: E402
import terrapulse_sources as sources  # noqa: E402

ARTIFACT = os.path.join(BACKEND, "data", "ner_cell_features.json")


def _artifact():
    if not os.path.exists(ARTIFACT):
        pytest.skip("cell features not built in this checkout")
    with io.open(ARTIFACT, encoding="utf-8") as fh:
        return json.load(fh)


# --- the detector ----------------------------------------------------------

def test_signature_covers_every_source_the_extractors_read():
    signature = sources.source_signature()
    for name in sources.NAMES:
        assert name in signature, name
        assert signature[name]["files"] > 0, name
        assert signature[name]["bytes"] > 0, name
    assert signature["digest"]


def test_an_unchanged_source_set_reports_nothing():
    current = sources.source_signature()
    assert sources.changed_sources(current, current) == []


def test_a_reissued_source_is_detected_even_when_the_size_is_identical():
    current = sources.source_signature()
    recorded = copy.deepcopy(current)
    recorded["landcover"]["newest_mtime"] = "1999-01-01T00:00:00"
    reasons = sources.changed_sources(recorded, current)
    assert len(reasons) == 1
    assert reasons[0].startswith("landcover")
    assert "republished" in reasons[0]


def test_a_changed_file_set_is_detected():
    current = sources.source_signature()
    recorded = copy.deepcopy(current)
    recorded["dem"]["files"] -= 1
    reasons = sources.changed_sources(recorded, current)
    assert len(reasons) == 1 and reasons[0].startswith("dem")


def test_a_new_source_file_is_detected_by_size_alone():
    current = sources.source_signature()
    recorded = copy.deepcopy(current)
    recorded["soil"]["bytes"] += 1
    reasons = sources.changed_sources(recorded, current)
    assert len(reasons) == 1 and reasons[0].startswith("soil")


def test_an_artifact_with_no_recorded_sources_is_treated_as_stale():
    reasons = sources.changed_sources({}, sources.source_signature())
    assert len(reasons) == 1
    assert "no source signature" in reasons[0]


# --- the artifact ----------------------------------------------------------

def test_cell_features_record_which_release_of_each_source_they_came_from():
    recorded = _artifact().get("sources") or {}
    assert recorded, "the artifact must record the inputs it was computed from"
    assert len(recorded["digest"]) >= 8


def test_the_stored_cell_features_still_describe_the_data_on_disk():
    recorded = _artifact()["sources"]
    assert pipeline._source_staleness() == [], \
        "a source moved; rerun scripts/extract_cell_features.py"


def test_stage_03_reports_where_its_numbers_came_from():
    result = pipeline.stage_03_geo(refresh=False)
    assert result.stage == "03"
    assert result.status == "ok"
    assert "sources_moved" in result.detail
    assert result.detail["cell_features"]["cells"] > 0
    assert result.detail["derivatives_example"]["dem_tile"].endswith(".tif")


def test_the_refresh_flag_gates_the_rebuild(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "_source_staleness", lambda: ["dem: republished"])
    monkeypatch.setattr(pipeline, "_rebuild_cell_features",
                        lambda: calls.append("rebuild") or True)

    off = pipeline.stage_03_geo(refresh=False)
    assert off.detail["cell_features_rebuilt"] is False
    assert off.detail["stale_note"]
    assert calls == []

    on = pipeline.stage_03_geo(refresh=True)
    assert on.detail["cell_features_rebuilt"] is True
    assert calls == ["rebuild"]


def test_nothing_is_rebuilt_when_the_sources_are_unchanged():
    result = pipeline.stage_03_geo(refresh=True)
    if result.detail["sources_moved"]:
        pytest.skip("a source genuinely moved; staged for rebuild")
    assert result.detail["cell_features_rebuilt"] is False