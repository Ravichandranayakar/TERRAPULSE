import csv
import json
from pathlib import Path

src = Path("TERRAPULSE_DATA/01_LANDSLIDE_LABELS/GSI_Landslide_Inventory.shp/GSI_Landslide_Inventory.geojson")
out_dir = Path("TERRAPULSE_DATA/07_GEOLOGY/GSI/derived")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "gsi_geology_ner.csv"

ner_states = {
    "Assam", "Arunachal Pradesh", "Meghalaya", "Mizoram",
    "Nagaland", "Manipur", "Tripura", "Sikkim",
}

data = json.loads(src.read_text(encoding="utf-8"))
rows = []

for feature in data["features"]:
    props = feature["properties"]

    if (props.get("STATE") or "").strip() not in ner_states:
        continue

    rows.append({
        "SLIDE_NO": props.get("SLIDE_NO"),
        "STATE": props.get("STATE"),
        "DISTRICT": props.get("DISTRICT"),
        "GEOLOGY": props.get("GEOLOGY"),
        "GEOMORPHOLOGY": props.get("GEOMORPHOLOGY"),
        "HYDROLOGICAL_CONDITION": props.get("HYDROLOGICAL_CONDITION"),
    })

with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Saved {len(rows)} NER geology rows to {out_path}")
