import os
import time
import requests

OUT = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\TERRAPULSE_DATA\08_LANDCOVER\ESA_WorldCover\2021_v200\raw"
os.makedirs(OUT, exist_ok=True)

BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"

tiles = ["N%dE%03d" % (la, lo) for la in (21, 24, 27) for lo in (87, 90, 93, 96)]

print("ESA WorldCover 2021 v200 - 12 tiles for NER")
print("Target:", OUT, "\n")

ok = skip = fail = 0
total_mb = 0.0

for t in tiles:
    url = BASE.format(tile=t)
    name = url.rsplit("/", 1)[-1]
    dest = os.path.join(OUT, name)
    part = dest + ".part"

    if os.path.exists(dest) and os.path.getsize(dest) > 1000000:
        mb = os.path.getsize(dest) / 1e6
        print("[=] exists  %s (%.1f MB)" % (name, mb))
        skip += 1
        total_mb += mb
        continue

    for attempt in range(1, 4):
        try:
            done = os.path.getsize(part) if os.path.exists(part) else 0
            headers = {"Range": "bytes=%d-" % done} if done else {}
            with requests.get(url, headers=headers, stream=True, timeout=180) as r:
                r.raise_for_status()
                if done and r.status_code == 206:
                    mode = "ab"
                else:
                    mode = "wb"
                    done = 0
                with open(part, mode) as f:
                    for chunk in r.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)
            os.replace(part, dest)
            mb = os.path.getsize(dest) / 1e6
            print("[+] %s  %.1f MB" % (name, mb))
            ok += 1
            total_mb += mb
            break
        except Exception as e:
            print("[!] attempt %d failed for %s: %s" % (attempt, name, e))
            time.sleep(3)
    else:
        print("[X] GAVE UP %s" % name)
        fail += 1

print("\nDownloaded: %d | Already present: %d | Failed: %d" % (ok, skip, fail))
print("Total size: %.1f MB" % total_mb)
print("Saved to:", OUT)
