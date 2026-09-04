"""
TerraPulse.ai — Geographic Data Module
North Eastern Region (NER) — Landslide Risk Monitoring
Focused on Sikkim (primary) — real lat/lon coordinates

Data Sources (Reference):
- GSI Landslide Hazard Zonation maps for Sikkim
- ISRO NRSC NER Landslide Atlas
- NH-10 route (Rangpo to Mangan) approximate coordinates
- Terrain profiles based on district geological surveys
"""

# ---------------------------------------------------------------------------
# MONITORING GRID CELLS — North Sikkim + surrounding districts
# Each cell represents a ~5km x 5km geographic monitoring unit
# ---------------------------------------------------------------------------
NER_GRID_CELLS = [
    {
        "location_id": "NSK_01", "name": "Mangan North Ridge",
        "district": "North Sikkim", "state": "Sikkim",
        "lat_min": 27.52, "lat_max": 27.57, "lon_min": 88.51, "lon_max": 88.56,
        "centroid_lat": 27.545, "centroid_lon": 88.535,
        "slope_angle": 42.0, "elevation_m": 1820, "aspect": "NW",
        "soil_type": "Weathered Gneiss", "rock_type": "Biotite Gneiss",
        "base_susceptibility": 0.72, "near_nh10": True, "historical_count": 8,
        "description": "Steep ridge above NH-10 corridor, high historical landslide frequency"
    },
    {
        "location_id": "NSK_02", "name": "Mangan Town Slope",
        "district": "North Sikkim", "state": "Sikkim",
        "lat_min": 27.50, "lat_max": 27.52, "lon_min": 88.52, "lon_max": 88.56,
        "centroid_lat": 27.510, "centroid_lon": 88.540,
        "slope_angle": 38.0, "elevation_m": 1650, "aspect": "SE",
        "soil_type": "Colluvial Soil", "rock_type": "Phyllite-Schist",
        "base_susceptibility": 0.65, "near_nh10": True, "historical_count": 5,
        "description": "Populated slope area near Mangan town, NH-10 passes below"
    },
    {
        "location_id": "NSK_03", "name": "Chungthang Upper Slope",
        "district": "North Sikkim", "state": "Sikkim",
        "lat_min": 27.58, "lat_max": 27.63, "lon_min": 88.62, "lon_max": 88.67,
        "centroid_lat": 27.605, "centroid_lon": 88.645,
        "slope_angle": 47.0, "elevation_m": 2210, "aspect": "W",
        "soil_type": "Phyllite Regolith", "rock_type": "Chlorite Phyllite",
        "base_susceptibility": 0.81, "near_nh10": False, "historical_count": 11,
        "description": "Very steep upper slopes above Teesta river confluence"
    },
    {
        "location_id": "NSK_04", "name": "Singhik High Zone",
        "district": "North Sikkim", "state": "Sikkim",
        "lat_min": 27.62, "lat_max": 27.67, "lon_min": 88.56, "lon_max": 88.61,
        "centroid_lat": 27.645, "centroid_lon": 88.585,
        "slope_angle": 51.0, "elevation_m": 2460, "aspect": "SW",
        "soil_type": "Schist-Gneiss Colluvium", "rock_type": "Garnet Schist",
        "base_susceptibility": 0.87, "near_nh10": False, "historical_count": 14,
        "description": "Highest susceptibility zone — extreme slope angles with fractured bedrock"
    },
    {
        "location_id": "NSK_05", "name": "Lachen Valley Floor",
        "district": "North Sikkim", "state": "Sikkim",
        "lat_min": 27.67, "lat_max": 27.72, "lon_min": 88.54, "lon_max": 88.59,
        "centroid_lat": 27.695, "centroid_lon": 88.565,
        "slope_angle": 18.0, "elevation_m": 2750, "aspect": "N",
        "soil_type": "Glacial Moraine", "rock_type": "Granite Gneiss",
        "base_susceptibility": 0.38, "near_nh10": False, "historical_count": 2,
        "description": "Relatively flat valley floor — lower slope angle reduces risk"
    },
    {
        "location_id": "NSK_06", "name": "Tashiding Escarpment",
        "district": "West Sikkim", "state": "Sikkim",
        "lat_min": 27.30, "lat_max": 27.35, "lon_min": 88.30, "lon_max": 88.35,
        "centroid_lat": 27.325, "centroid_lon": 88.325,
        "slope_angle": 44.0, "elevation_m": 1580, "aspect": "NE",
        "soil_type": "Laterite Clay", "rock_type": "Quartzite-Schist",
        "base_susceptibility": 0.68, "near_nh10": False, "historical_count": 6,
        "description": "West Sikkim escarpment zone — clay-rich soil prone to saturation"
    },
    {
        "location_id": "NSK_07", "name": "Dikchu NH-10 Section",
        "district": "East Sikkim", "state": "Sikkim",
        "lat_min": 27.33, "lat_max": 27.38, "lon_min": 88.57, "lon_max": 88.62,
        "centroid_lat": 27.355, "centroid_lon": 88.595,
        "slope_angle": 36.0, "elevation_m": 960, "aspect": "SE",
        "soil_type": "Alluvial-Colluvial Fill", "rock_type": "Meta-Sedimentary",
        "base_susceptibility": 0.55, "near_nh10": True, "historical_count": 4,
        "description": "Teesta valley section — NH-10 cut slopes frequently destabilised"
    },
    {
        "location_id": "NSK_08", "name": "Rangpo Entry Zone",
        "district": "East Sikkim", "state": "Sikkim",
        "lat_min": 27.16, "lat_max": 27.21, "lon_min": 88.52, "lon_max": 88.57,
        "centroid_lat": 27.185, "centroid_lon": 88.545,
        "slope_angle": 22.0, "elevation_m": 620, "aspect": "NW",
        "soil_type": "River Terrace Deposit", "rock_type": "Alluvial",
        "base_susceptibility": 0.28, "near_nh10": True, "historical_count": 1,
        "description": "Lower elevation entry zone — gentler slopes reduce susceptibility"
    },
    {
        "location_id": "NSK_09", "name": "Namchi Hill Station",
        "district": "South Sikkim", "state": "Sikkim",
        "lat_min": 27.15, "lat_max": 27.20, "lon_min": 88.34, "lon_max": 88.39,
        "centroid_lat": 27.175, "centroid_lon": 88.365,
        "slope_angle": 40.0, "elevation_m": 1370, "aspect": "E",
        "soil_type": "Regolith Debris", "rock_type": "Dolomitic Limestone",
        "base_susceptibility": 0.62, "near_nh10": False, "historical_count": 7,
        "description": "South Sikkim hill station area — road cuttings increase instability"
    },
    {
        "location_id": "NSK_10", "name": "Gangtok-Dikchu Corridor",
        "district": "East Sikkim", "state": "Sikkim",
        "lat_min": 27.31, "lat_max": 27.36, "lon_min": 88.59, "lon_max": 88.64,
        "centroid_lat": 27.335, "centroid_lon": 88.615,
        "slope_angle": 35.0, "elevation_m": 1540, "aspect": "W",
        "soil_type": "Colluvial Soil", "rock_type": "Mica Schist",
        "base_susceptibility": 0.58, "near_nh10": True, "historical_count": 9,
        "description": "High-traffic corridor — NH-10 adjacent slopes with frequent minor slides"
    },
]

# ---------------------------------------------------------------------------
# NH-10 HIGHWAY ROUTE WAYPOINTS
# National Highway 10 — Rangpo to Mangan (Sikkim Lifeline Road)
# Approximate real waypoints along the Teesta River valley
# ---------------------------------------------------------------------------
NH10_ROUTE = [
    [27.185, 88.545],   # Rangpo (entry point into Sikkim from West Bengal)
    [27.220, 88.555],   # Near Singtam
    [27.265, 88.560],
    [27.310, 88.572],   # Ranipool junction
    [27.340, 88.588],
    [27.355, 88.595],   # Dikchu bridge
    [27.395, 88.578],
    [27.435, 88.560],
    [27.470, 88.548],
    [27.510, 88.542],   # Mangan approach
    [27.545, 88.535],   # Mangan North
]

# ---------------------------------------------------------------------------
# HISTORICAL LANDSLIDE INVENTORY
# Based on GSI NER Inventory + ISRO Landslide Atlas records for Sikkim
# Used as reference markers on the map (clearly labelled as historical records)
# ---------------------------------------------------------------------------
HISTORICAL_LANDSLIDES = [
    {
        "id": "LS_001", "lat": 27.548, "lon": 88.533,
        "date": "2023-07-14", "type": "Debris Flow",
        "trigger": "Extreme antecedent rainfall followed by intense monsoonal event",
        "impact": "NH-10 blocked for 48 hours, 2 vehicles damaged",
        "rainfall_trigger": "3-day accumulated: approx 280-320mm",
        "location_ref": "NSK_01"
    },
    {
        "id": "LS_002", "lat": 27.612, "lon": 88.648,
        "date": "2022-06-20", "type": "Rotational Slide",
        "trigger": "Sustained antecedent rainfall combined with seismic activity",
        "impact": "1 village partially evacuated, agricultural land affected",
        "rainfall_trigger": "7-day antecedent: approx 180mm",
        "location_ref": "NSK_03"
    },
    {
        "id": "LS_003", "lat": 27.649, "lon": 88.582,
        "date": "2023-08-02", "type": "Rock Fall with Debris Avalanche",
        "trigger": "Intense monsoonal rainfall on saturated high-angle slope",
        "impact": "Road closure, 3 fatalities reported",
        "rainfall_trigger": "24h intensity: approx 85mm/hr",
        "location_ref": "NSK_04"
    },
    {
        "id": "LS_004", "lat": 27.513, "lon": 88.543,
        "date": "2022-07-08", "type": "Shallow Translational Slide",
        "trigger": "High antecedent saturation followed by intense rain event",
        "impact": "NH-10 disrupted for 8 hours",
        "rainfall_trigger": "3-day accumulated: approx 210mm",
        "location_ref": "NSK_02"
    },
    {
        "id": "LS_005", "lat": 27.178, "lon": 88.367,
        "date": "2021-09-15", "type": "Debris Flow",
        "trigger": "Prolonged low-intensity monsoonal rainfall",
        "impact": "Agricultural land loss, minor road damage",
        "rainfall_trigger": "7-day antecedent: approx 220mm",
        "location_ref": "NSK_09"
    },
    {
        "id": "LS_006", "lat": 27.337, "lon": 88.618,
        "date": "2023-06-30", "type": "Planar Slide",
        "trigger": "Intense rainfall event on road cut slope",
        "impact": "NH-10 disrupted for 12 hours",
        "rainfall_trigger": "24h: approx 120mm",
        "location_ref": "NSK_10"
    },
    {
        "id": "LS_007", "lat": 27.645, "lon": 88.592,
        "date": "2021-07-28", "type": "Multiple Debris Flows",
        "trigger": "Multi-day extreme rainfall during peak monsoon",
        "impact": "Road access cut for 3 days, emergency response delayed",
        "rainfall_trigger": "3-day accumulated: approx 350mm",
        "location_ref": "NSK_04"
    },
]

# ---------------------------------------------------------------------------
# INFRASTRUCTURE ASSETS (for impact-aware risk assessment)
# ---------------------------------------------------------------------------
INFRASTRUCTURE = {
    "highways": [
        {"name": "NH-10", "description": "Sikkim Lifeline — Rangpo to Mangan", "route": NH10_ROUTE, "critical": True}
    ],
    "settlements": [
        {"name": "Mangan Town", "lat": 27.510, "lon": 88.540, "population": 12000, "critical": True},
        {"name": "Singhik Village", "lat": 27.645, "lon": 88.585, "population": 800, "critical": False},
        {"name": "Chungthang", "lat": 27.605, "lon": 88.645, "population": 2500, "critical": False},
        {"name": "Dikchu", "lat": 27.355, "lon": 88.595, "population": 1800, "critical": False},
    ]
}
