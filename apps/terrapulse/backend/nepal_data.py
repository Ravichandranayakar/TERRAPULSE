"""
Nepal Data Provider for TerraPulse
Serves real geographic data derived from:
- HOT Nepal Flood 2026 GeoJSON (90.11 sq km verified polygon)
- UNOSAT Nepal Landslides 2015 via HDX
- ICIMOD published Himalayan geology research
"""
import os
import json

_PROCESSED_PATH = os.path.join(os.path.dirname(__file__), 'data', 'nepal', 'nepal_processed.json')

def get_nepal_data():
    if not os.path.exists(_PROCESSED_PATH):
        raise FileNotFoundError("nepal_processed.json not found. Run build_nepal2.py to regenerate.")
    with open(_PROCESSED_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data
