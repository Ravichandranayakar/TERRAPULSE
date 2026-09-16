"""The satellite layer: window summaries and the observation attached to a cell.

These run on synthetic rasters so they need no network and no downloaded scene.
"""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

import satellite_ingest as si
import satellite_watch


def _write(path, array, dtype="int16"):
    profile = {"driver": "GTiff", "height": array.shape[0], "width": array.shape[1],
               "count": 1, "dtype": dtype, "crs": "EPSG:32645",
               "transform": from_origin(500000, 3000000, 10, 10)}
    with rasterio.open(str(path), "w", **profile) as dst:
        dst.write(array.astype(dtype), 1)
    return str(path)


def test_ndvi_is_computed_from_red_and_nir(tmp_path):
    red = _write(tmp_path / "red.tif", np.full((8, 8), 1000))
    nir = _write(tmp_path / "nir.tif", np.full((8, 8), 3000))
    out = si.optical_summary(red, nir)
    assert out["usable"] is True
    assert out["ndvi_mean"] == pytest.approx(0.5, abs=1e-6)


def test_cloud_is_excluded_before_the_average(tmp_path):
    # Left half vegetated, right half cloud. Masking must leave only the left.
    red = np.full((8, 8), 1000, dtype="int16")
    nir = np.full((8, 8), 3000, dtype="int16")
    nir[:, 4:] = 9000  # cloud reads as absurdly bright
    scl = np.full((8, 8), 4, dtype="uint8")   # 4 = vegetation
    scl[:, 4:] = 9                            # 9 = cloud

    out = si.optical_summary(_write(tmp_path / "red.tif", red),
                             _write(tmp_path / "nir.tif", nir),
                             _write(tmp_path / "scl.tif", scl, dtype="uint8"))
    assert out["usable_fraction"] == pytest.approx(0.5, abs=1e-6)
    assert out["ndvi_mean"] == pytest.approx(0.5, abs=1e-6)


def test_a_window_that_is_all_cloud_is_not_averaged(tmp_path):
    red = _write(tmp_path / "red.tif", np.full((8, 8), 1000))
    nir = _write(tmp_path / "nir.tif", np.full((8, 8), 3000))
    scl = _write(tmp_path / "scl.tif", np.full((8, 8), 9, dtype="uint8"), dtype="uint8")
    out = si.optical_summary(red, nir, scl)
    assert out["usable"] is False
    assert "cloud-free" in out["reason"]


def test_sar_reports_backscatter_and_ratio(tmp_path):
    out = si.sar_summary(_write(tmp_path / "vv.tif", np.full((8, 8), 200)),
                         _write(tmp_path / "vh.tif", np.full((8, 8), 100)))
    assert out["usable"] is True
    assert out["vv_dn_mean"] == pytest.approx(200.0)
    assert out["vv_vh_ratio_db"] == pytest.approx(10 * np.log10(2.0), abs=0.01)


def test_summarise_cell_keeps_optical_and_sar_apart(tmp_path):
    bands = {
        "red": _write(tmp_path / "red.tif", np.full((8, 8), 1000)),
        "nir": _write(tmp_path / "nir.tif", np.full((8, 8), 3000)),
        "vv": _write(tmp_path / "vv.tif", np.full((8, 8), 200)),
        "vh": _write(tmp_path / "vh.tif", np.full((8, 8), 100)),
    }
    result = {"cell_id": "NSK_01",
              "downloaded": [dict(band=b, path=p, scene="S" + b, datetime="2026-08-11T00:00:00Z")
                             for b, p in bands.items()],
              "skipped": []}
    out = si.summarise_cell(result)
    assert out["available"] is True
    assert out["optical"]["scene"] == "Sred"
    assert out["sar"]["scene"] == "Svv"
    assert out["optical"]["ndvi_mean"] == pytest.approx(0.5, abs=1e-6)


def test_a_cell_with_no_scene_says_so_instead_of_inventing_one():
    out = si.summarise_cell({"cell_id": "NSK_02", "downloaded": [],
                             "skipped": ["sentinel2: no scene in 60 days"]})
    assert out["available"] is False
    assert "no scene" in out["reason"]
    assert "optical" not in out and "sar" not in out


def test_scratch_windows_are_reachable_but_status_needs_no_download():
    status = satellite_watch.status()
    for key in ("runs", "generated_at", "cells_with_imagery", "cells_total", "role"):
        assert key in status
    assert "not a model input" in (status["role"] or "")


def test_the_s3_mirror_url_is_rewritten_for_gdal():
    url = "s3://sentinel-s1-l1c/GRD/2026/9/16/x/measurement/iw-vv.tiff"
    out = si._readable_url(url)
    assert out.startswith("https://sentinel-s1-l1c.s3.amazonaws.com/")
    assert out.endswith("measurement/iw-vv.tiff")
    plain = "https://example.com/a.tif"
    assert si._readable_url(plain) == plain