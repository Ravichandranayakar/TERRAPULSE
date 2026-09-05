from geo_data import NER_GRID_CELLS, NH10_ROUTE, HISTORICAL_LANDSLIDES, INFRASTRUCTURE as NER_INFRA
from nepal_data import get_nepal_data

def get_ner_data():
    return {
        "grid_cells": NER_GRID_CELLS,
        "nh10_route": NH10_ROUTE,
        "historical_landslides": HISTORICAL_LANDSLIDES,
        "infrastructure": NER_INFRA,
        "historical_events": HISTORICAL_LANDSLIDES,
        "region_name": "NER (India)",
        "region_id": "ner_india"
    }

def get_region_data(region_id: str):
    if region_id == 'nepal_case':
        return get_nepal_data()
    # Default to NER for SIH Demo
    return get_ner_data()
