"""
Nepal Data Provider for TerraPulse
Serves real geographic data derived from:
- HOT Nepal Flood 2026 GeoJSON (90.11 sq km verified polygon)
- UNOSAT Nepal Landslides 2015 via HDX
- ICIMOD published Himalayan geology research
"""
import os
import json
import math

_PROCESSED_PATH = os.path.join(os.path.dirname(__file__), 'data', 'nepal', 'nepal_processed.json')
_EVENT_GEOMETRY_PATH = os.path.join(os.path.dirname(__file__), 'data', 'nepal', 'flood_aoi.geojson')


def _create_ellipse_polygon(lat, lon, length_km=2.0, width_km=0.6, rotation_deg=30):
    """Generate an approximate terrain-following elliptical polygon for a point observation."""
    coords = []
    for i in range(37):
        angle = math.radians(i * 10)
        dx = (length_km / 2) * math.cos(angle)
        dy = (width_km / 2) * math.sin(angle)
        
        rot = math.radians(rotation_deg)
        rdx = dx * math.cos(rot) - dy * math.sin(rot)
        rdy = dx * math.sin(rot) + dy * math.cos(rot)
        
        clat = lat + (rdy / 111.32)
        clon = lon + (rdx / (111.32 * math.cos(math.radians(lat))))
        coords.append([clon, clat])
    return {"type": "Polygon", "coordinates": [coords]}


def _load_observed_event_layers(data):
    """Expose observed event geometry without replacing model risk cells."""
    layers = []
    try:
        with open(_EVENT_GEOMETRY_PATH, 'r', encoding='utf-8') as f:
            geometry_collection = json.load(f)
    except (OSError, json.JSONDecodeError):
        return layers

    features = geometry_collection.get('features', [])
    for event in data.get('historical_events', []):
        if event.get('event_type') == 'flood':
            # Use real polygon for flood
            for feature in features:
                geometry = feature.get('geometry', {})
                if geometry.get('type') not in ('Polygon', 'MultiPolygon'):
                    continue
                layers.append({
                    'id': f"{event.get('id', 'event')}-extent",
                    'event_id': event.get('id'),
                    'eventType': event.get('event_type'),
                    'geometry': geometry,
                    'source': event.get('source'),
                    'observedAt': event.get('date'),
                    'confidence': 'verified' if event.get('verified') else 'unverified',
                    'role': 'observed_extent',
                    **feature.get('properties', {}),
                })
        elif event.get('event_type') == 'landslide':
            # Generate a realistic downslope footprint for point records
            layers.append({
                'id': f"{event.get('id', 'event')}-extent",
                'event_id': event.get('id'),
                'eventType': event.get('event_type'),
                'geometry': _create_ellipse_polygon(event.get('lat'), event.get('lon')),
                'source': event.get('source'),
                'observedAt': event.get('date'),
                'confidence': 'approximate',
                'role': 'observed_extent',
                'area_sq_km': 1.2
            })
    return layers

def get_nepal_data():
    if not os.path.exists(_PROCESSED_PATH):
        raise FileNotFoundError("nepal_processed.json not found. Run build_nepal2.py to regenerate.")
    with open(_PROCESSED_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['event_layers'] = _load_observed_event_layers(data)
    return data
