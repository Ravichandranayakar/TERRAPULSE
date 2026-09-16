"""
Stage 01 - Satellite ingestion (Sentinel-1 SAR + Sentinel-2 optical).

Source
  Earth Search STAC v1 (Element 84), which indexes the AWS Open Data mirrors of
  the Copernicus archive. No account, no API key, no quota: the scenes are the
  same public COGs, and STAC is only the index that finds them.

Why windowed reads instead of whole scenes
  A Sentinel-2 L2A tile is ~1 GB. A monitoring cell is a 5 km box. Every band is
  a Cloud-Optimised GeoTIFF, so GDAL can read just the few hundred pixels that
  cover the cell over HTTP range requests. That turns a 1 GB download into a few
  MB and makes a per-cell refresh practical.

What this provides to the pipeline
  - Sentinel-2: recent optical reflectance -> new cut slopes and bare ground that
    the annual land-cover product will not show until its next release.
  - Sentinel-1: SAR backscatter -> sees through cloud, which matters because the
    monsoon that triggers landslides also hides the ground from optical sensors.

Cadence
  Sentinel-2 revisits every ~5 days, Sentinel-1 every ~6-12 days, and cloud can
  push usable optical passes further apart. This is a scheduled pull, not a
  stream:  the pipeline re-queries on every cycle, and simply receives whatever
  has been published since the last one.

Accuracy of the window placement
  Sentinel-2 L2A tiles are georeferenced, so the window is placed exactly. A
  Sentinel-1 GRD measurement TIFF has no geotransform, only ground control
  points, so its window is placed by a local affine fitted to the three nearest
  control points. That is accurate to roughly one control-point spacing: good
  enough to say "this cell looks like this", not good enough for change
  detection against a survey. It is reported as such rather than presented as
  an exact crop.
"""

import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"

COLLECTIONS = {"sentinel2": "sentinel-2-l2a", "sentinel1": "sentinel-1-grd"}

# Bands that carry the signal we need, kept small on purpose.
S2_ASSETS = ["blue", "green", "red", "nir", "scl"]
S1_ASSETS = ["vv", "vh"]

WINDOW_PX = 256


def _readable_url(url: str) -> str:
    """A URL GDAL can actually fetch.

    The STAC index reports the Sentinel-1 mirror as s3://sentinel-s1-l1c/...
    and GDAL has no S3 driver here, so the band would be dropped for a reason
    that has nothing to do with the data. The same objects answer anonymously
    over the HTTPS endpoint, so the scheme is rewritten instead.
    """
    if url.startswith("s3://"):
        bucket, _, key = url[5:].partition("/")
        return "https://%s.s3.amazonaws.com/%s" % (bucket, key)
    return url


def _gcp_index(src, lon: float, lat: float):
    """Approximate pixel for a lon/lat on a product that carries GCPs only.

    Sentinel-1 GRD measurement TIFFs have no geotransform, so the pixel cannot be
    computed directly. A local affine fitted to the three nearest ground control
    points lands within about one control-point spacing - enough to place a 256 px
    window, but not survey accurate. Returns (row, col) or None.
    """
    import numpy as np
    from rasterio.warp import transform as warp_transform

    points, crs = src.gcps
    if not points:
        return None
    if crs is not None and str(crs).upper() != "EPSG:4326":
        lon, lat = warp_transform("EPSG:4326", crs, [lon], [lat])
        lon, lat = lon[0], lat[0]

    xs = np.array([p.x for p in points], dtype="float64")
    ys = np.array([p.y for p in points], dtype="float64")
    near = np.argsort((xs - lon) ** 2 + (ys - lat) ** 2)[:3]
    design = np.array([[xs[i], ys[i], 1.0] for i in near])
    rows = np.array([points[i].row for i in near], dtype="float64")
    cols = np.array([points[i].col for i in near], dtype="float64")
    try:
        row_coeffs = np.linalg.solve(design, rows)
        col_coeffs = np.linalg.solve(design, cols)
    except np.linalg.LinAlgError:
        return None
    return (row_coeffs[0] * lon + row_coeffs[1] * lat + row_coeffs[2],
            col_coeffs[0] * lon + col_coeffs[1] * lat + col_coeffs[2])


def _bbox(lat: float, lon: float, pad_deg: float = 0.03) -> List[float]:
    return [lon - pad_deg, lat - pad_deg, lon + pad_deg, lat + pad_deg]


def search_scenes(lat: float, lon: float, collection: str,
                  days_back: int = 30, max_cloud: Optional[float] = 60.0,
                  limit: int = 3, timeout: float = 30.0) -> List[Dict[str, Any]]:
    """Most recent scenes covering a point. Returns STAC items, newest first."""
    import httpx

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)

    body: Dict[str, Any] = {
        "collections": [collection],
        "bbox": _bbox(lat, lon),
        "datetime": "%s/%s" % (start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               end.strftime("%Y-%m-%dT%H:%M:%SZ")),
        "limit": limit,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }
    if max_cloud is not None and collection == COLLECTIONS["sentinel2"]:
        body["query"] = {"eo:cloud_cover": {"lt": max_cloud}}

    response = httpx.post(STAC_SEARCH, json=body, timeout=timeout)
    response.raise_for_status()
    return response.json().get("features", [])


def available_scenes(cells: List[Dict[str, Any]], days_back: int = 30) -> Dict[str, Any]:
    """What imagery exists for each cell right now. No pixel download."""
    out: Dict[str, Any] = {"sentinel2": {}, "sentinel1": {}}
    for cell in cells:
        cid = cell.get("location_id")
        lat, lon = cell.get("centroid_lat"), cell.get("centroid_lon")
        if lat is None or lon is None:
            continue
        for key, collection in COLLECTIONS.items():
            try:
                items = search_scenes(lat, lon, collection, days_back=days_back, limit=2)
                out[key][cid] = [
                    {
                        "id": it.get("id"),
                        "datetime": it.get("properties", {}).get("datetime"),
                        "cloud_cover": it.get("properties", {}).get("eo:cloud_cover"),
                        "platform": it.get("properties", {}).get("platform"),
                        "assets": sorted((it.get("assets") or {}).keys()),
                    }
                    for it in items
                ]
            except Exception as error:
                logger.warning("[Satellite] %s %s search failed: %s", key, cid, error)
                out[key][cid] = {"error": str(error)}
    return out


def download_cell_window(asset_url: str, lat: float, lon: float,
                         out_path: str, size: int = WINDOW_PX) -> Optional[str]:
    """Read a small window around a point from a remote COG over HTTP.

    Uses GDAL's /vsicurl/ so only the needed byte ranges of the COG are fetched.
    """
    import rasterio
    from rasterio.warp import transform as warp_transform
    from rasterio.windows import Window

    try:
        with rasterio.open("/vsicurl/" + _readable_url(asset_url)) as src:
            # A Sentinel scene is in its own projected CRS, so a lon/lat pair
            # means nothing to src.index() until it is transformed. Passing the
            # degrees straight in lands on the wrong part of the scene - for an
            # optical tile that is a corner sliver, and for a GRD product, which
            # has no CRS at all, it is the same arbitrary window for every cell.
            if src.crs is not None:
                xs, ys = warp_transform("EPSG:4326", src.crs, [lon], [lat])
                row, col = src.index(xs[0], ys[0])
            else:
                approx = _gcp_index(src, lon, lat)
                if approx is None:
                    raise ValueError("scene has neither a CRS nor ground control "
                                     "points, so the cell cannot be located")
                row, col = int(round(approx[0])), int(round(approx[1]))

            half = size // 2
            # Keep the window fully inside the raster so it is always size x size
            # rather than a sliver against an edge.
            r0 = max(0, min(row - half, max(0, src.height - size)))
            c0 = max(0, min(col - half, max(0, src.width - size)))
            r1 = min(src.height, r0 + size)
            c1 = min(src.width, c0 + size)
            window = Window(c0, r0, c1 - c0, r1 - r0)

            data = src.read(1, window=window)
            profile = src.profile.copy()
            profile.update(window=None, height=data.shape[0], width=data.shape[1],
                           count=1, transform=src.window_transform(window))

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data, 1)
        return out_path
    except Exception as error:
        logger.warning("[Satellite] window read failed (%s): %s", asset_url, error)
        return None


def ingest_cell(cell: Dict[str, Any], out_dir: str, days_back: int = 30) -> Dict[str, Any]:
    """Fetch the newest optical + SAR window for one cell."""
    cid = cell.get("location_id")
    lat, lon = cell.get("centroid_lat"), cell.get("centroid_lon")
    result: Dict[str, Any] = {"cell_id": cid, "downloaded": [], "skipped": []}

    if lat is None or lon is None:
        result["skipped"].append("no centroid")
        return result

    for key, collection in COLLECTIONS.items():
        assets_wanted = S2_ASSETS if key == "sentinel2" else S1_ASSETS
        try:
            items = search_scenes(lat, lon, collection, days_back=days_back, limit=1)
        except Exception as error:
            result["skipped"].append("%s search failed: %s" % (key, error))
            continue

        if not items:
            result["skipped"].append("%s: no scene in %d days" % (key, days_back))
            continue

        item = items[0]
        assets = item.get("assets") or {}
        for band in assets_wanted:
            asset = assets.get(band)
            if not asset or not asset.get("href"):
                continue
            name = "%s_%s_%s_%s.tif" % (cid, key, band, str(item["id"])[:28])
            path = os.path.join(out_dir, name)
            # A cached window still has to report which scene it came from, or a
            # second run loses the scene date the first run knew.
            stamp = {"band": band, "path": path, "scene": item.get("id"),
                     "datetime": item.get("properties", {}).get("datetime")}
            if os.path.exists(path):
                result["downloaded"].append(dict(stamp, cached=True))
                continue
            written = download_cell_window(asset["href"], lat, lon, path)
            if written:
                result["downloaded"].append({
                    "band": band,
                    "path": written,
                    "scene": item.get("id"),
                    "datetime": item.get("properties", {}).get("datetime"),
                    "cached": False,
                })

    return result


SCL_USABLE = {4, 5, 6, 7}  # vegetation, not-vegetated, water, unclassified


def _band(path: str):
    """One band, with the product's own scale and offset applied."""
    import numpy as np
    import rasterio

    with rasterio.open(path) as src:
        data = src.read(1).astype("float64")
        scale = src.scales[0] if src.scales else 1.0
        offset = src.offsets[0] if src.offsets else 0.0
        nodata = src.nodata
    if scale != 1.0 or offset != 0.0:
        data = data * scale + offset
    if nodata is not None:
        data = np.where(data == nodata * scale + offset, np.nan, data)
    return data


def optical_summary(red_path: str, nir_path: str,
                    scl_path: Optional[str] = None) -> Dict[str, Any]:
    """NDVI over the window, restricted to ground the scene actually sees.

    A window over Sikkim in monsoon is mostly cloud, and an NDVI averaged over
    cloud is a number about cloud. The scene classification layer is downloaded
    for exactly this reason, so cloud, shadow and snow are excluded before the
    average is taken, and the usable fraction is reported with it.
    """
    import numpy as np

    red = _band(red_path)
    nir = _band(nir_path)
    denominator = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where(np.abs(denominator) > 1e-9,
                        (nir - red) / denominator, np.nan)

    mask = np.isfinite(ndvi)
    if scl_path and os.path.exists(scl_path):
        import rasterio

        with rasterio.open(scl_path) as src:
            scl = src.read(1)
        if scl.shape == ndvi.shape:
            mask = mask & np.isin(scl, list(SCL_USABLE))

    values = ndvi[mask]
    if values.size == 0:
        return {"usable": False, "reason": "no cloud-free ground in this window"}
    return {
        "usable": True,
        "ndvi_mean": round(float(values.mean()), 4),
        "ndvi_p10": round(float(np.percentile(values, 10)), 4),
        "ndvi_p90": round(float(np.percentile(values, 90)), 4),
        "usable_pixels": int(values.size),
        "window_pixels": int(ndvi.size),
        "usable_fraction": round(float(values.size) / float(ndvi.size), 4),
    }


def sar_summary(vv_path: str, vh_path: Optional[str] = None) -> Dict[str, Any]:
    """Mean backscatter over the window.

    Raw DN, not calibrated sigma0: calibration needs the annotation XML, which is
    not downloaded here. Useful as a relative signal between passes, and labelled
    as DN so it is never mistaken for a calibrated radiometric product.
    """
    import numpy as np

    vv = _band(vv_path)
    if not np.isfinite(vv).any():
        return {"usable": False, "reason": "window contained no valid samples"}
    out: Dict[str, Any] = {"usable": True, "vv_dn_mean": round(float(np.nanmean(vv)), 2)}
    if vh_path and os.path.exists(vh_path):
        vh = _band(vh_path)
        if np.isfinite(vh).any():
            vh_mean = float(np.nanmean(vh))
            out["vh_dn_mean"] = round(vh_mean, 2)
            if vh_mean:
                ratio = float(np.nanmean(vv)) / vh_mean
                if ratio > 0:
                    out["vv_vh_ratio_db"] = round(10.0 * float(np.log10(ratio)), 2)
    return out


def summarise_cell(result: Dict[str, Any]) -> Dict[str, Any]:
    """Turn one cell's downloaded windows into a readable observation."""
    optical_bands: Dict[str, Dict[str, Any]] = {}
    sar_bands: Dict[str, Dict[str, Any]] = {}
    for entry in result.get("downloaded") or []:
        target = sar_bands if entry.get("band") in S1_ASSETS else optical_bands
        target[entry.get("band")] = entry

    observation: Dict[str, Any] = {"cell_id": result.get("cell_id")}

    if "red" in optical_bands and "nir" in optical_bands:
        head = optical_bands["red"]
        observation["optical"] = optical_summary(
            optical_bands["red"]["path"],
            optical_bands["nir"]["path"],
            (optical_bands.get("scl") or {}).get("path"),
        )
        observation["optical"]["scene"] = head.get("scene")
        observation["optical"]["datetime"] = head.get("datetime")

    if "vv" in sar_bands:
        head = sar_bands["vv"]
        observation["sar"] = sar_summary(
            sar_bands["vv"]["path"],
            (sar_bands.get("vh") or {}).get("path"),
        )
        observation["sar"]["scene"] = head.get("scene")
        observation["sar"]["datetime"] = head.get("datetime")

    if "optical" not in observation and "sar" not in observation:
        observation["available"] = False
        observation["reason"] = "; ".join(result.get("skipped") or []) or "no scene found"
    else:
        observation["available"] = True
    return observation


def ingest(cells: List[Dict[str, Any]], out_dir: str,
           days_back: int = 30) -> Dict[str, Any]:
    """Ingest imagery for every cell. Returns a manifest."""
    os.makedirs(out_dir, exist_ok=True)
    results = [ingest_cell(cell, out_dir, days_back) for cell in cells]

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Earth Search STAC v1 (AWS Open Data Sentinel mirrors)",
        "collections": COLLECTIONS,
        "days_back": days_back,
        "cells": results,
        "bands_downloaded": sum(len(r["downloaded"]) for r in results),
        "cells_with_imagery": sum(1 for r in results if r["downloaded"]),
    }
    with io.open(os.path.join(out_dir, "ingest_manifest.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest