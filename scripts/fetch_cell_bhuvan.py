"""
Fetch Bhuvan geomorphology and lineament features at the 10 monitoring cells.

The trained model reads these two layers, so the live map has to be able to hand
them over. The cells are not part of the 17,092 training points, so they need
their own pull.

This reuses scripts/bhuvan_fetch_points.py unchanged - the same WMS
GetFeatureInfo calls on the same GSI/ISRO layers that produced the training
columns, so the map and the training table describe the ground the same way.

Output
  TERRAPULSE_DATA/07_GEOLOGY/Bhuvan/cell_points.csv        the 10 cell centroids
  TERRAPULSE_DATA/07_GEOLOGY/Bhuvan/cell_bhuvan_out.csv   their layer values
"""

import csv
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BACKEND = os.path.join(REPO, "apps", "terrapulse", "backend")
OUT_DIR = os.path.join(REPO, "TERRAPULSE_DATA", "07_GEOLOGY", "Bhuvan")
POINTS = os.path.join(OUT_DIR, "cell_points.csv")
OUT = os.path.join(OUT_DIR, "cell_bhuvan_out.csv")

sys.path.insert(0, BACKEND)
import geo_data  # noqa: E402


def write_points():
    os.makedirs(OUT_DIR, exist_ok=True)
    with io.open(POINTS, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "lon", "lat", "STATE"])
        for cell in geo_data.NER_GRID_CELLS:
            writer.writerow([cell["location_id"], cell["centroid_lon"],
                             cell["centroid_lat"], cell["state"]])
    print("wrote %s (%d cells)" % (POINTS, len(geo_data.NER_GRID_CELLS)))


def main():
    write_points()
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "bhuvan_fetch_points.py"), POINTS, OUT],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (proc.stdout or "")[-1500:]
    if tail:
        print(tail)
    if proc.returncode != 0 or not os.path.exists(OUT):
        print((proc.stderr or "")[-1500:])
        return 1
    with io.open(OUT, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    ok = sum(1 for r in rows if (r.get("geomorph_l1") or "").strip())
    lin = sum(1 for r in rows if (r.get("lineament_dist_km") or "").strip())
    print("cells                       : %d" % len(rows))
    print("with geomorphology          : %d" % ok)
    print("with a lineament distance   : %d" % lin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())