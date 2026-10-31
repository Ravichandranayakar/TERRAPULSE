
import csv
from pathlib import Path

import requests

base_url = "https://maps.isric.org/mapserv"
out_dir = Path("TERRAPULSE_DATA/06_SOIL/SoilGrids/raw")
out_dir.mkdir(parents=True, exist_ok=True)

properties = ["clay", "sand", "silt", "soc", "bdod", "nitrogen"]
depth = "0-5cm"

for prop in properties:
    coverage = f"{prop}_{depth}_mean"
    params = [
          ("map", f"/map/{prop}.map"),
          ("SERVICE", "WCS"),
          ("VERSION", "2.0.1"),
          ("REQUEST", "GetCoverage"),
          ("COVERAGEID", coverage),
          ("FORMAT", "image/tiff"),
          ("SUBSET", "long(87,98)"),
          ("SUBSET", "lat(21,30)"),
          ("SUBSETTINGCRS", "http://www.opengis.net/def/crs/EPSG/0/4326"),
          ("OUTPUTCRS", "http://www.opengis.net/def/crs/EPSG/0/4326"),
      ]

    path = out_dir / f"{coverage}.tif"

    if path.exists() and path.stat().st_size > 1024:
          print(f"Already exists: {path.name}")
          continue

    print(f"Downloading {coverage} ...")
    response = requests.get(base_url, params=params, timeout=300)
    response.raise_for_status()

    path.write_bytes(response.content)
    print(f"Saved {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")