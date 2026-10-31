from pathlib import Path

import requests

url = "https://download.geofabrik.de/asia/india-latest-free.shp.zip"
out_dir = Path("TERRAPULSE_DATA/09_INFRASTRUCTURE/OSM/raw")
out_dir.mkdir(parents=True, exist_ok=True)

path = out_dir / "india-latest-free.shp.zip"

if path.exists() and path.stat().st_size > 1024:
      print(f"Already exists: {path.name}")
else:
  with requests.get(url, stream=True, timeout=(30, 600)) as r:
        r.raise_for_status()
  with open(path, "wb") as f:
      for chunk in r.iter_content(chunk_size=1024 * 1024):
          if chunk:
              f.write(chunk)

print(f"Saved: {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)")