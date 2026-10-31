"""One place that knows which source files feed the feature extractors.

Used by two callers:

  scripts/extract_cell_features.py      fingerprints its inputs when it writes
  backend/pipeline.py                   compares, and rebuilds when they move

Kept free of heavy imports (no rasterio, no pandas, no geopandas) so the
pipeline can import it on every cycle without paying for a geospatial stack.

The signature of a source is (file count, total bytes, newest mtime). If any of
those move, the source was republished and the derived numbers are stale.
"""

import glob
import hashlib
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(REPO, "TERRAPULSE_DATA")

# (name, folder, glob) for every dataset the extractors read.
SOURCE_SPEC = [
    ("dem", os.path.join(ROOT, "05_TERRAIN", "Copernicus_DEM", "GLO30", "raw"), "*.tif"),
    ("landcover", os.path.join(ROOT, "08_LANDCOVER", "ESA_WorldCover", "2021_v200", "raw"), "*.tif"),
    ("soil", os.path.join(ROOT, "06_SOIL", "SoilGrids", "raw"), "*.tif"),
    ("rainfall", os.path.join(ROOT, "04_RAINFALL", "IMD_RF25", "rainfall"), "*.nc"),
    ("osm", os.path.join(ROOT, "09_INFRASTRUCTURE", "OSM", "extracted"), "*.shp"),
]

NAMES = [name for name, _, _ in SOURCE_SPEC]


def folder_signature(folder, pattern):
    """(file count, total bytes, newest mtime) for one folder."""
    files = glob.glob(os.path.join(folder, pattern))
    newest = 0.0
    total = 0
    for path in files:
        try:
            stat = os.stat(path)
        except OSError:
            continue
        newest = max(newest, stat.st_mtime)
        total += stat.st_size
    return files, len(files), total, newest


def source_signature():
    """Fingerprint of every source dataset, plus a combined digest."""
    signature = {}
    parts = []
    for name, folder, pattern in SOURCE_SPEC:
        _, count, total, newest = folder_signature(folder, pattern)
        signature[name] = {
            "folder": os.path.relpath(folder, REPO),
            "files": count,
            "bytes": total,
            "newest_mtime": (time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(newest))
                             if newest else None),
        }
        parts.append("%s:%d:%d:%.0f" % (name, count, total, newest))
    signature["digest"] = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return signature


def changed_sources(recorded, current):
    """Which sources moved since the artifact was written.

    Returns a list of human readable reasons; empty means the derived numbers
    are still describing the data on disk.
    """
    reasons = []
    if not recorded:
        return ["no source signature recorded with this artifact"]
    for name in NAMES:
        was = recorded.get(name) or {}
        now = current.get(name) or {}
        if not was:
            reasons.append("%s: not recorded" % name)
            continue
        if (was.get("files"), was.get("bytes")) != (now.get("files"), now.get("bytes")):
            reasons.append("%s: file set changed (%s -> %s files, %s -> %s bytes)"
                           % (name, was.get("files"), now.get("files"),
                              was.get("bytes"), now.get("bytes")))
        elif was.get("newest_mtime") != now.get("newest_mtime"):
            reasons.append("%s: republished (%s -> %s)"
                           % (name, was.get("newest_mtime"), now.get("newest_mtime")))
    return reasons