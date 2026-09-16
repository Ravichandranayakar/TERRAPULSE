"""Tests for the live ingest -> features -> model -> alert cycle."""

from datetime import datetime, timedelta

import live_pipeline
from live_conditions import IST, _now_index, summarise_cell


def _series(hours_before=48, hours_after=24, precip=0.0, soil=0.30):
    """A series shaped like the Open-Meteo response: past, then future."""
    now = datetime.now(IST).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    out = []
    for h in range(-hours_before, hours_after + 1):
        t = now + timedelta(hours=h)
        out.append({
            "time": t.isoformat(),
            "precipitation": precip,
            "precip_probability": 0.0,
            "wind_speed": 0.0,
            "soil_moisture_0_to_7cm": soil,
            "soil_moisture_7_to_28cm": soil - 0.01,
            "temperature_2m": 18.0,
            "synthetic": False,
        })
    return out


def _all_synthetic(hours=24):
    now = datetime.now(IST).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    return [{"time": (now + timedelta(hours=h)).isoformat(), "precipitation": 5.0,
             "precip_probability": 0, "wind_speed": 0, "soil_moisture_0_to_7cm": None,
             "soil_moisture_7_to_28cm": None, "temperature_2m": None, "synthetic": True}
            for h in range(-hours, 1)]


# --- trigger bands ---------------------------------------------------------

def test_trigger_is_none_when_dry():
    cond = {"available": True, "rainfall_24h_mm": 2.0, "rainfall_3d_mm": 5.0,
            "rainfall_7d_mm": 10.0}
    assert live_pipeline.classify_trigger(cond)["level"] == "NONE"


def test_trigger_is_watch_at_half_the_recorded_threshold():
    cond = {"available": True, "rainfall_24h_mm": 50.0, "rainfall_3d_mm": 60.0,
            "rainfall_7d_mm": 70.0}
    result = live_pipeline.classify_trigger(cond)
    assert result["level"] == "WATCH"
    assert result["driver"] == "rainfall_24h_mm"


def test_trigger_is_alert_at_the_recorded_threshold():
    cond = {"available": True, "rainfall_24h_mm": 100.0, "rainfall_3d_mm": 0.0,
            "rainfall_7d_mm": 0.0}
    result = live_pipeline.classify_trigger(cond)
    assert result["level"] == "ALERT"
    assert result["exceeded"] == ["rainfall_24h_mm"]


def test_trigger_is_severe_at_one_and_a_half_times():
    cond = {"available": True, "rainfall_24h_mm": 0.0, "rainfall_3d_mm": 0.0,
            "rainfall_7d_mm": 270.0}
    assert live_pipeline.classify_trigger(cond)["level"] == "SEVERE"


def test_trigger_is_unknown_without_a_measurement():
    result = live_pipeline.classify_trigger({"available": False, "reason": "api down"})
    assert result["level"] == "UNKNOWN"
    assert result["index"] == -1


def test_seven_day_total_drives_the_band_not_just_today():
    """"A dry day after a wet week must not read as safe."""
    cond = {"available": True, "rainfall_24h_mm": 0.0, "rainfall_3d_mm": 0.0,
            "rainfall_7d_mm": 200.0}
    assert live_pipeline.classify_trigger(cond)["level"] == "ALERT"


# --- combining model susceptibility with the live trigger ------------------

def test_alert_is_the_higher_of_the_two_components():
    quiet = live_pipeline.combine("HIGH", 0)
    assert quiet["alert_level"] == "HIGH"

    wet = live_pipeline.combine("LOW", 2)
    assert wet["alert_level"] == "HIGH"


def test_both_high_escalates_to_critical():
    result = live_pipeline.combine("HIGH", 2)
    assert result["alert_level"] == "CRITICAL"
    assert result["escalated_because_both_high"] is True


def test_moderate_susceptibility_with_a_watch_stays_moderate():
    result = live_pipeline.combine("MODERATE", 1)
    assert result["alert_level"] == "MODERATE"
    assert result["escalated_because_both_high"] is False


def test_both_components_are_reported_for_the_jury():
    result = live_pipeline.combine("HIGH", 1)
    assert result["susceptibility_component"] == "HIGH"
    assert result["trigger_component"] == "WATCH"
    assert "rule" in result


# --- soil moisture scaling -------------------------------------------------

def test_soil_moisture_is_scaled_to_a_zero_one_index():
    assert live_pipeline._soil_moisture_index(0.25) == 0.5
    assert live_pipeline._soil_moisture_index(0.50) == 1.0
    assert live_pipeline._soil_moisture_index(0.90) == 1.0


def test_soil_moisture_missing_stays_missing():
    assert live_pipeline._soil_moisture_index(None) is None


# --- series reduction ------------------------------------------------------

def test_now_index_ignores_future_hours():
    series = _series(hours_before=48, hours_after=24)
    idx = _now_index(series)
    assert series[idx]["time"] <= series[-1]["time"]
    assert idx == 48


def test_antecedent_windows_are_real_sums():
    series = _series(hours_before=200, hours_after=0, precip=1.0)
    out = summarise_cell("TEST", series)
    assert out["available"] is True
    assert out["rainfall_24h_mm"] == 24.0
    assert out["rainfall_3d_mm"] == 72.0
    assert out["rainfall_7d_mm"] == 168.0


def test_a_wet_week_is_not_inflated_by_a_multiplier():
    """The old code returned 24h * 5.0 for the 7-day total, which is wrong."""
    series = _series(hours_before=200, hours_after=0, precip=1.0)
    out = summarise_cell("TEST", series)
    assert out["rainfall_7d_mm"] == sum(
        e["precipitation"] for e in series[-168:])
    assert out["rainfall_7d_mm"] != out["rainfall_24h_mm"] * 5.0


def test_soil_moisture_is_reported_from_measurement():
    series = _series(hours_before=48, hours_after=0, soil=0.45)
    out = summarise_cell("TEST", series)
    assert out["soil_moisture_0_to_7cm"] == 0.45
    assert out["soil_moisture_0_to_7cm_7d_max"] == 0.45


def test_synthetic_series_is_never_reported_as_a_measurement():
    """A fabricated number must not be able to cross a rainfall threshold."""
    out = summarise_cell("TEST", _all_synthetic())
    assert out["available"] is False
    assert "reason" in out
    assert "rainfall_24h_mm" not in out


def test_empty_series_is_unavailable():
    out = summarise_cell("TEST", [])
    assert out["available"] is False


# --- honesty guard ---------------------------------------------------------

def test_live_rainfall_is_never_written_into_the_climatology_slot():
    """The model feature must stay a 35-year average.

    Feeding today's rain into `rain_clim_annual_mm` would make the model read a
    monsoonal cell as having a near-desert climate. This guards the boundary.
    """
    import io
    import json
    with io.open(live_pipeline.CELL_FEATURES, encoding="utf-8") as fh:
        artifact = json.load(fh)

    live_keys = {"rainfall_1h_mm", "rainfall_24h_mm", "rainfall_3d_mm",
                 "rainfall_7d_mm", "soil_moisture_0_to_7cm"}
    for cell in artifact["cells"].values():
        static = cell["static_features"]
        assert not (live_keys & set(static)), "live measurement leaked into static features"
        assert static["rain_clim_annual_mm"] > 500, "climatology is not an annual total"