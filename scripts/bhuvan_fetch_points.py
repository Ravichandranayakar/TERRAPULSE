"""
Fetch Bhuvan (ISRO/NRSC) geomorphology + lineament distance at point locations.

Why a script and not a download:
  bhuvan-vec2.nrsc.gov.in serves WMS only. WFS is disabled ("Service WFS is
  disabled"), so there is no bulk vector download. The reliable path is WMS
  GetFeatureInfo with info_format=application/json, which returns real geometry.

Leakage warning:
  Run this on POSITIVE and NEGATIVE point sets alike. If only landslide points
  carry a geomorphology value, the model learns "value present = landslide".
  Keep coverage symmetric or the feature is unusable.

Query design (measured against real NER landslide points, not assumed):
  Geomorphology - areal polygons, so the point lies inside one. Small box for a
  precise point-in-polygon pick; no buffer needed.
        box 0.02 deg, 512 px  ->  ~4.3 m pixel
  Lineaments - sparse lines. Measured density near NER landslides is roughly
  0-11 features within 25 km, and nearest offsets of 0.46-0.55 km were observed,
  so a small radius finds nothing. We search wide and then compute the true
  nearest distance in Python.
        box 0.50 deg, 1024 px, buffer 500 px  ->  ~27 km search radius
  lineament_dist_km is the true point-to-segment distance to the closest mapped
  lineament (0.0 if the point sits on one). It is blank when the layer has no
  features in range - which is real: Sikkim and Assam returned none even at 27 km.

Usage:
    python bhuvan_fetch_points.py
        reads whichever of ner_landslide_points.csv (positives) or
        ner_negative_points.csv (negatives) is beside this script, and writes
        bhuvan_out.csv or bhuvan_out_negative.csv respectively

    python bhuvan_fetch_points.py <points.csv> <out.csv> [--delay 0.4] [--limit N]
        explicit paths, if you prefer

Points CSV must have lon/lat columns. Recognised names (case-insensitive):
    lon, longitude, x, LONGITUDE      lat, latitude, y, LATITUDE
An id column is auto-detected (SLIDE_NO, id, fid) and echoed back.
A state column named 'STATE' is used to pick the correct per-state layer.

Resumable: re-running skips ids already present in <out.csv>.
"""

import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

WMS = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?"

STATE_CODE = {
    "arunachal pradesh": "AR", "assam": "AS", "meghalaya": "ML",
    "manipur": "MN", "mizoram": "MZ", "nagaland": "NL",
    "sikkim": "SK", "tripura": "TR",
}

GM_LAYER = "geomorphology:{c}_GM50K_0506"
LN_LAYER = "lineament:{c}_LN50K_0506"

GEO_BOX, GEO_PX, GEO_BUF = 0.02, 512, 0
LIN_BOX, LIN_PX, LIN_BUF = 0.50, 1024, 500

LON_KEYS = ("lon", "longitude", "x")
LAT_KEYS = ("lat", "latitude", "y")
ID_KEYS = ("slide_no", "id", "fid", "objectid")

OUT_COLS = [
    "id", "lon", "lat", "state_code",
    "geomorph_des", "geomorph_l1", "geomorph_l2",
    "lineament_dist_km", "lineament_n", "lineament_des", "lineament_mag",
    "status",
]


def pick_key(header, keys):
    return next((k for k in header if k.strip().lower() in keys), None)


def gfi(layer, lon, lat, box, px, buf, feature_count=200, timeout=60):
    bbox = "%.6f,%.6f,%.6f,%.6f" % (lon - box / 2, lat - box / 2,
                                    lon + box / 2, lat + box / 2)
    q = urllib.parse.urlencode({
        "service": "WMS", "version": "1.1.1", "request": "GetFeatureInfo",
        "layers": layer, "query_layers": layer, "srs": "EPSG:4326",
        "bbox": bbox, "width": px, "height": px,
        "x": px // 2, "y": px // 2,
        "info_format": "application/json",
        "feature_count": feature_count, "buffer": buf,
    })
    with urllib.request.urlopen(WMS + q, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    if not raw.strip().startswith("{"):
        raise ValueError("non-JSON response (layer absent or error)")
    return json.loads(raw)


def iter_segments(geom):
    """Yield ((x1,y1),(x2,y2)) in lon/lat for any line-ish geometry."""
    if not geom:
        return
    t = geom.get("type")
    if t == "LineString":
        parts = [geom["coordinates"]]
    elif t == "MultiLineString":
        parts = geom["coordinates"]
    else:
        return
    for line in parts:
        for i in range(len(line) - 1):
            yield line[i], line[i + 1]


def dist_point_to_segment_km(lon, lat, a, b):
    """Accurate for the <50 km scales we query: local equirectangular metres."""
    kx = 111320.0 * math.cos(math.radians(lat))
    ky = 110540.0
    px, py = 0.0, 0.0
    ax, ay = (a[0] - lon) * kx, (a[1] - lat) * ky
    bx, by = (b[0] - lon) * kx, (b[1] - lat) * ky
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(ax, ay) / 1000.0
    t = -(ax * dx + ay * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(cx - px, cy - py) / 1000.0


def fetch_one(lon, lat, code, delay):
    out = {"geomorph_des": "", "geomorph_l1": "", "geomorph_l2": "",
           "lineament_dist_km": "", "lineament_n": 0,
           "lineament_des": "", "lineament_mag": "", "status": ""}

    try:
        g = gfi(GM_LAYER.format(c=code), lon, lat, GEO_BOX, GEO_PX, GEO_BUF)
        feats = g.get("features", [])
        if feats:
            p = feats[0].get("properties", {})
            out["geomorph_des"] = str(p.get("Des", "")).strip()
            out["geomorph_l1"] = p.get("Level1", "")
            out["geomorph_l2"] = p.get("Level2", "")
        else:
            out["status"] = "geo_empty"
    except Exception as e:
        out["status"] = "geo_err:%s" % str(e)[:40]

    time.sleep(delay)

    try:
        g = gfi(LN_LAYER.format(c=code), lon, lat, LIN_BOX, LIN_PX, LIN_BUF)
        feats = g.get("features", [])
        out["lineament_n"] = len(feats)
        best = None
        for feat in feats:
            for a, b in iter_segments(feat.get("geometry")):
                d = dist_point_to_segment_km(lon, lat, a, b)
                if best is None or d < best:
                    best = d
        if best is not None:
            out["lineament_dist_km"] = round(best, 4)
            p = feats[0].get("properties", {})
            out["lineament_des"] = str(p.get("Des", "")).strip()
            out["lineament_mag"] = p.get("Magnitude", "")
    except Exception as e:
        st = out["status"]
        out["status"] = (st + ";" if st else "") + "lin_err:%s" % str(e)[:40]

    time.sleep(delay)
    return out


def main():
    HERE = os.path.dirname(os.path.abspath(__file__))

    ap = argparse.ArgumentParser()
    ap.add_argument("points", nargs="?",
                    help="points CSV. Default: whichever NER points file is "
                         "beside this script (positives first, then negatives).")
    ap.add_argument("out", nargs="?",
                    help="output CSV. Default: bhuvan_out.csv for the positive "
                         "points, bhuvan_out_negative.csv for the negative points.")
    ap.add_argument("--delay", type=float, default=0.4,
                    help="seconds between requests; be polite (default 0.4)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N new points")
    args = ap.parse_args()

    # A laptop running only the negative half does not have the positive points
    # file, and vice versa. Resolve the input by what is actually present rather
    # than assuming a name, so the same unedited script runs on every machine.
    if not args.points:
        cands = [os.path.join(HERE, "ner_landslide_points.csv"),
                 os.path.join(HERE, "ner_negative_points.csv")]
        present = [c for c in cands if os.path.exists(c)]
        if not present:
            sys.exit("no points file found.\n"
                     "Put ner_landslide_points.csv (positives) or "
                     "ner_negative_points.csv (negatives) beside this script,\n"
                     "or pass the path yourself:\n"
                     "  python bhuvan_fetch_points.py <points.csv> <out.csv>")
        args.points = present[0]
    if not os.path.exists(args.points):
        sys.exit("points file not found: %s" % args.points)

    # Derive the output name from the input, so a negative run can never append
    # into the positive run's file sitting in the same folder.
    if not args.out:
        is_neg = "negative" in os.path.basename(args.points).lower()
        args.out = os.path.join(
            os.getcwd(), "bhuvan_out_negative.csv" if is_neg else "bhuvan_out.csv")

    with open(args.points, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        header = reader.fieldnames or []
    if not rows:
        sys.exit("no rows in %s" % args.points)

    lon_k = pick_key(header, LON_KEYS)
    lat_k = pick_key(header, LAT_KEYS)
    id_k = pick_key(header, ID_KEYS)
    st_k = pick_key(header, ("state",))
    if not lon_k or not lat_k:
        sys.exit("could not find lon/lat columns in %s" % header)

    print("points file : %s (%d rows)" % (args.points, len(rows)))
    print("lon/lat     : %s / %s" % (lon_k, lat_k))
    print("id col      : %s    state col: %s" % (id_k, st_k))

    done = set()
    if os.path.exists(args.out) and os.path.getsize(args.out) > 0:
        with open(args.out, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                done.add(r.get("id", ""))
        print("resuming    : %d already done" % len(done))
    else:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=OUT_COLS).writeheader()

    handled = errors = skipped = 0
    t0 = time.time()

    with open(args.out, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLS)
        todo = len(rows) - len(done)

        for i, row in enumerate(rows, 1):
            pid = str(row.get(id_k, i) if id_k else i)
            if pid in done:
                continue
            try:
                lon = float(row[lon_k]); lat = float(row[lat_k])
            except (TypeError, ValueError):
                skipped += 1
                continue

            sname = str(row.get(st_k, "") or "").strip().lower() if st_k else ""
            code = STATE_CODE.get(sname)
            if code is None:
                skipped += 1
                continue

            if code == "MZ":
                w.writerow({"id": pid, "lon": lon, "lat": lat, "state_code": "MZ",
                            "status": "layer_absent_on_bhuvan"})
                fh.flush(); handled += 1
                continue

            res = fetch_one(lon, lat, code, args.delay)
            res.update({"id": pid, "lon": lon, "lat": lat, "state_code": code})
            w.writerow(res); fh.flush()
            handled += 1
            if res["status"]:
                errors += 1

            if handled % 25 == 0:
                el = time.time() - t0
                rate = handled / el if el else 0
                left = (todo - handled) / rate / 60 if rate else 0
                print("  %5d/%d  handled=%d err=%d  %.2f pt/s  ~%.1f min left"
                      % (i, len(rows), handled, errors, rate, left))

            if args.limit and handled >= args.limit:
                print("limit reached"); break

    print("\ndone. handled=%d  skipped=%d  with_errors=%d" % (handled, skipped, errors))
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()