import os
import time
import csv
from pathlib import Path
import requests

# Run from the TERRAPULSE project root
output_dir = Path("TERRAPULSE_DATA/05_TERRAIN/Copernicus_DEM/GLO30/raw")
derived_dir = Path("TERRAPULSE_DATA/05_TERRAIN/Copernicus_DEM/GLO30/derived")
output_dir.mkdir(parents=True, exist_ok=True)
derived_dir.mkdir(parents=True, exist_ok=True)

lat_min, lat_max = 21, 29
lon_min, lon_max = 87, 97

base_url = "https://copernicus-dem-30m.s3.amazonaws.com"
manifest_path = output_dir / "download_manifest.csv"

session = requests.Session()
session.headers.update({"User-Agent": "TerraPulse-DEM-Downloader/1.0"})

downloaded = 0
already = 0
missing = 0
failed = 0
manifest_rows = []

print(f"Downloading Copernicus DEM GLO-30 for Lat {lat_min}-{lat_max}, Lon {lon_min}-{lon_max}")

for lat in range(lat_min, lat_max + 1):
    for lon in range(lon_min, lon_max + 1):
        tile_name = f"Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM"
        filename = f"{tile_name}.tif"
        file_path = output_dir / filename

        if file_path.exists() and file_path.stat().st_size > 1024:
            print(f"[=] Already exists: {filename}")
            already += 1
            manifest_rows.append({"tile": tile_name, "status": "already_exists", "path": str(file_path)})
            continue

        url = f"{base_url}/{tile_name}/{filename}"
        part_path = output_dir / f"{filename}.part"
        ok = False

        for attempt in range(1, 4):
            try:
                  with session.get(url, stream=True, timeout=(30, 300)) as response:
                      if response.status_code == 404:
                          print(f"[!] Not on S3 (water/sea tile): {tile_name}")
                          missing += 1
                          manifest_rows.append({"tile": tile_name, "status": "not_found", "path": ""})
                          ok = True
                          break

                      response.raise_for_status()
                      total = int(response.headers.get("Content-Length", 0))

                      with open(part_path, "wb") as f:
                          for chunk in response.iter_content(chunk_size=1024 * 1024):
                              if chunk:
                                  f.write(chunk)

                  os.replace(part_path, file_path)
                  size_mb = file_path.stat().st_size / (1024 * 1024)
                  print(f"[+] Downloaded: {filename} ({size_mb:.1f} MB)")
                  downloaded += 1
                  manifest_rows.append({"tile": tile_name, "status": "downloaded", "path": str(file_path)})
                  ok = True
                  break

            except requests.exceptions.RequestException as exc:
                  print(f"[X] Attempt {attempt}/3 failed for {tile_name}: {exc}")
                  if part_path.exists():
                      part_path.unlink()
                  time.sleep(2 * attempt)

            if not ok:
              failed += 1
              manifest_rows.append({"tile": tile_name, "status": "failed", "path": ""})

    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
      writer = csv.DictWriter(f, fieldnames=["tile", "status", "path"])
      writer.writeheader()
      writer.writerows(manifest_rows)

    print("\nDone")
    print(f"Downloaded: {downloaded}")
    print(f"Already present: {already}")
    print(f"Missing/water: {missing}")
    print(f"Failed: {failed}")
    print(f"Saved to: {output_dir}")
    print(f"Manifest: {manifest_path}")
