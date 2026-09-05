import re

with open('apps/terrapulse/backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update init_db to seed both regions
init_db_old = '''        # Seed locations from geo_data
        existing = conn.execute("SELECT COUNT(*) FROM monitoring_locations").fetchone()[0]
        if existing == 0:
            for cell in NER_GRID_CELLS:'''

init_db_new = '''        # Seed locations from all regions
        existing = conn.execute("SELECT COUNT(*) FROM monitoring_locations").fetchone()[0]
        if existing == 0:
            from regions import get_region_data
            all_cells = get_region_data("ner_india")["grid_cells"] + get_region_data("nepal_case")["grid_cells"]
            for cell in all_cells:'''
content = content.replace(init_db_old, init_db_new)

# 2. Fix import in init_db
content = content.replace('from geo_data import NER_GRID_CELLS\n', '')

# 3. Update get_geo_data
get_geo_data_old = '''def get_geo_data():
    """Return geographic data: locations, NH-10 route, historical landslides."""
    from geo_data import NER_GRID_CELLS, NH10_ROUTE, HISTORICAL_LANDSLIDES, INFRASTRUCTURE
    return {
        "grid_cells": NER_GRID_CELLS,
        "nh10_route": NH10_ROUTE,
        "historical_landslides": HISTORICAL_LANDSLIDES,
        "infrastructure": INFRASTRUCTURE,
    }'''

get_geo_data_new = '''def get_geo_data(region_id: str = "ner_india"):
    """Return geographic data dynamically based on the active region configuration."""
    from regions import get_region_data
    return get_region_data(region_id)'''
content = content.replace(get_geo_data_old, get_geo_data_new)

# 4. Update get_forecast to accept region_id
forecast_old = '''@app.get("/api/forecast")
async def get_forecast():'''

forecast_new = '''@app.get("/api/forecast")
async def get_forecast(region_id: str = "ner_india"):'''
content = content.replace(forecast_old, forecast_new)

# 5. Update the get_locations call in get_forecast to filter by region
# Wait, the frontend is currently hitting /api/forecast but does it get ALL locations? 
# Let's just pass region_id to get_locations() if it exists. But wait, get_locations() reads from the DB. Let's see if get_locations takes a region.
# It doesn't currently. The prompt says we need to abstract geo_data.
# The UI will request data with ?region_id=... on the endpoints.

with open('apps/terrapulse/backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
