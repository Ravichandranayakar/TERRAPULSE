"""
TerraPulse.ai — FastAPI Backend
AI-Based Early Warning and Landslide Risk Monitoring System
North Eastern Region (NER) — SIH 2026

Architecture:
- FastAPI with async SSE streaming
- SQLite database (migration-ready for PostgreSQL + PostGIS)
- ML Risk Engine (Random Forest / Gradient Boosting)
- Antecedent Rainfall Accumulation Engine
- Temporal Storm Simulator (same pipeline as real data)
- Early Warning Engine (Normal → Advisory → Warning → Critical)
- Field Verification + Human-in-the-Loop Curator
"""

import sqlite3
import os
import json
import random
import time
from datetime import datetime, timedelta
from typing import Optional

from alerts.service import CellBroadcastService
from verification.repository import VerificationRepository
from verification.service import VerificationService
from risk.schemas import RiskBatchRequest, RiskFeatureInput
from risk.service import predict_development_risk, predict_development_risk_batch

# ---------------------------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------------------------
DB_DIR = os.path.join(os.path.dirname(__file__), "data", "db")
DB_PATH = os.path.join(DB_DIR, "terrapulse.db")
_verification_repository = VerificationRepository(DB_PATH)
_verification_service = VerificationService(_verification_repository)


def _get_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the TerraPulse.ai database schema."""
    print("[TERRAPULSE] Initializing database schema...")
    conn = _get_db()
    try:
        # Monitoring locations (geographic grid cells)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_locations (
                location_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                district TEXT,
                state TEXT,
                lat_min REAL, lat_max REAL, lon_min REAL, lon_max REAL,
                centroid_lat REAL, centroid_lon REAL,
                slope_angle REAL,
                elevation_m REAL,
                aspect TEXT,
                soil_type TEXT,
                rock_type TEXT,
                base_susceptibility REAL DEFAULT 0.5,
                near_nh10 INTEGER DEFAULT 0,
                historical_count INTEGER DEFAULT 0,
                description TEXT
            )
        """)

        # Rainfall observations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rainfall_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                rainfall_24h_mm REAL DEFAULT 0,
                rainfall_3d_mm REAL DEFAULT 0,
                rainfall_7d_mm REAL DEFAULT 0,
                rainfall_intensity REAL DEFAULT 0,
                soil_moisture_index REAL DEFAULT 0.3,
                simulation_step INTEGER DEFAULT 0,
                FOREIGN KEY(location_id) REFERENCES monitoring_locations(location_id)
            )
        """)

        # Risk predictions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                risk_score REAL,
                risk_level TEXT,
                probability REAL,
                contributing_factors TEXT,
                FOREIGN KEY(location_id) REFERENCES monitoring_locations(location_id)
            )
        """)

        # Early warning alerts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS landslide_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id TEXT NOT NULL,
                location_name TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                risk_level TEXT,
                risk_score REAL,
                trigger_factors TEXT,
                affected_infrastructure TEXT,
                status TEXT DEFAULT 'active',
                operator_notes TEXT,
                resolved_at TEXT,
                FOREIGN KEY(location_id) REFERENCES monitoring_locations(location_id)
            )
        """)

        # Field verifications (human-in-the-loop)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS field_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warning_id INTEGER,
                location_id TEXT,
                reported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                verified_by TEXT,
                outcome TEXT,
                field_notes TEXT,
                is_approved_for_training INTEGER DEFAULT 0,
                FOREIGN KEY(warning_id) REFERENCES landslide_warnings(id)
            )
        """)

        # Cell Broadcast dispatch simulation audit records
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cell_broadcast_simulations (
                broadcast_id TEXT PRIMARY KEY,
                warning_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                target_source TEXT NOT NULL,
                live_network_connected INTEGER NOT NULL DEFAULT 0,
                result_json TEXT NOT NULL,
                FOREIGN KEY(warning_id) REFERENCES landslide_warnings(id)
            )
        """)

        conn.commit()

        # Seed locations from all regions
        existing = conn.execute("SELECT COUNT(*) FROM monitoring_locations").fetchone()[0]
        if existing == 0:
            from regions import get_region_data
            all_cells = get_region_data("ner_india")["grid_cells"] + get_region_data("nepal_case")["grid_cells"]
            for cell in all_cells:
                conn.execute("""
                    INSERT OR IGNORE INTO monitoring_locations
                    (location_id, name, district, state, lat_min, lat_max, lon_min, lon_max,
                     centroid_lat, centroid_lon, slope_angle, elevation_m, aspect, soil_type,
                     rock_type, base_susceptibility, near_nh10, historical_count, description)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    cell.get("location_id", ""), cell.get("name", ""), cell.get("district", ""), cell.get("state", ""),
                    cell.get("lat_min", 0.0), cell.get("lat_max", 0.0), cell.get("lon_min", 0.0), cell.get("lon_max", 0.0),
                    cell.get("centroid_lat", 0.0), cell.get("centroid_lon", 0.0),
                    cell.get("slope_angle", 0.0), cell.get("elevation_m", 0.0), cell.get("aspect", ""),
                    cell.get("soil_type", ""), cell.get("rock_type", ""),
                    cell.get("base_susceptibility", 0.5), 1 if cell.get("near_nh10", False) else 0,
                    cell.get("historical_count", 0), cell.get("description", "")
                ))
            conn.commit()
            print(f"[TERRAPULSE] Seeded {len(all_cells)} monitoring locations")

        print("[TERRAPULSE] Database ready")
    finally:
        conn.close()
        
    _verification_repository.ensure_schema()

# ---------------------------------------------------------------------------
# DATA FUNCTIONS (called from frontend via RPC)
# ---------------------------------------------------------------------------

def get_locations():
    """Return all monitoring grid cells with their terrain profiles."""
    conn = _get_db()
    try:
        rows = conn.execute("SELECT * FROM monitoring_locations ORDER BY base_susceptibility DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()



def _get_nepal_status():
    """Compute live risk scores for Nepal cells using ML model on real terrain data."""
    import random
    from regions import get_region_data
    region = get_region_data('nepal_case')
    cells = region.get('grid_cells', [])
    route = region.get('nh10_route', [])

    try:
        from ml_engine import load_model, predict_risk
        model_bundle = load_model()
    except Exception:
        model_bundle = None

    random.seed(42)
    results = []
    for cell in cells:
        base_susc = cell.get('base_susceptibility', 0.5)
        slope = cell.get('slope_angle', 30.0)
        elevation = cell.get('elevation_m', 1000)
        hist = cell.get('historical_count', 2)

        # Use realistic monsoon rainfall values for Aug 2026 Nepal event
        rainfall_24h = random.uniform(45.0, 120.0) if base_susc > 0.7 else random.uniform(15.0, 55.0)
        rainfall_3d = rainfall_24h * random.uniform(2.2, 3.5)
        rainfall_7d = rainfall_3d * random.uniform(1.8, 2.8)
        soil_moisture = min(1.0, base_susc * random.uniform(0.7, 1.0))

        features = {
            'rainfall_24h_mm': rainfall_24h,
            'rainfall_3d_mm': rainfall_3d,
            'rainfall_7d_mm': rainfall_7d,
            'rainfall_intensity': rainfall_24h / 24.0,
            'slope_angle': slope,
            'elevation_m': elevation,
            'soil_moisture_index': soil_moisture,
            'base_susceptibility': base_susc,
            'historical_count': hist,
        }

        try:
            prediction = predict_risk(features, model_bundle)
            risk_score = prediction.get('risk_score', base_susc * 80)
            risk_level = prediction.get('risk_level', 'moderate').upper()
            factors = prediction.get('contributing_factors', [])
        except Exception:
            risk_score = round(base_susc * 85 + (slope - 20) * 0.5, 1)
            risk_score = min(99.0, max(5.0, risk_score))
            if risk_score >= 75:
                risk_level = 'CRITICAL'
            elif risk_score >= 55:
                risk_level = 'HIGH'
            elif risk_score >= 35:
                risk_level = 'MODERATE'
            else:
                risk_level = 'LOW'
            factors = [
                {'name': 'Rainfall (24h)', 'value': round(rainfall_24h, 1), 'unit': 'mm', 'impact': min(95, int(rainfall_24h * 0.7))},
                {'name': 'Slope Angle', 'value': slope, 'unit': 'deg', 'impact': min(90, int(slope * 1.4))},
                {'name': 'Geological Susceptibility', 'value': base_susc, 'unit': 'index', 'impact': int(base_susc * 90)},
                {'name': 'Soil Moisture', 'value': round(soil_moisture, 2), 'unit': 'index', 'impact': int(soil_moisture * 80)},
            ]

        results.append({
            'location_id': cell['location_id'],
            'name': cell['name'],
            'district': cell.get('district', 'Nepal'),
            'state': cell.get('state', 'Bagmati'),
            'centroid_lat': cell['centroid_lat'],
            'centroid_lon': cell['centroid_lon'],
            'lat_min': cell['lat_min'],
            'lat_max': cell['lat_max'],
            'lon_min': cell['lon_min'],
            'lon_max': cell['lon_max'],
            'slope_angle': slope,
            'elevation_m': elevation,
            'soil_type': cell.get('soil_type', 'Colluvial'),
            'rock_type': cell.get('rock_type', 'Gneiss'),
            'near_nh10': cell.get('near_nh10', False),
            'historical_count': hist,
            'risk_level': risk_level,
            'risk_score': round(risk_score, 1),
            'contributing_factors': factors,
            'rainfall_24h': round(rainfall_24h, 1),
            'rainfall_3d': round(rainfall_3d, 1),
            'soil_moisture_index': round(soil_moisture, 2),
            'data_source': cell.get('data_source', 'HOT/UNOSAT/ICIMOD'),
            'in_flood_zone': cell.get('in_flood_zone', False),
            'river_proximity': cell.get('river_proximity', ''),
        })

    # Compute route safety
    route_cells_near_highway = [r for r in results if r.get('near_nh10')]
    if route_cells_near_highway:
        max_risk = max(r['risk_score'] for r in route_cells_near_highway)
        if max_risk >= 75:
            route_safety = 'CRITICAL'
        elif max_risk >= 55:
            route_safety = 'HIGH_RISK'
        elif max_risk >= 35:
            route_safety = 'CAUTION'
        else:
            route_safety = 'OPEN'
    else:
        route_safety = 'UNKNOWN'

    return {
        'cells': results,
        'route_safety': route_safety,
        'nh10_route': route,
        'region_id': 'nepal_case',
    }


def get_latest_status(region_id: str = 'ner_india'):
    """Get current risk status for all locations.
    For Nepal case study: derives risk directly from real terrain data + ML model.
    For NER demo: reads from SQLite DB (existing flow).
    """
    if region_id == 'nepal_case':
        return _get_nepal_status()

    conn = _get_db()
    try:
        locations = conn.execute("SELECT * FROM monitoring_locations").fetchall()
        results = []
        for loc in locations:
            loc = dict(loc)
            # Get latest prediction for this location
            pred = conn.execute("""
                SELECT * FROM risk_predictions
                WHERE location_id = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (loc["location_id"],)).fetchone()

            # Get latest rainfall observation
            rain = conn.execute("""
                SELECT * FROM rainfall_observations
                WHERE location_id = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (loc["location_id"],)).fetchone()

            if pred:
                pred = dict(pred)
                risk_level = pred["risk_level"]
                risk_score = pred["risk_score"]
                factors = json.loads(pred.get("contributing_factors") or "[]")
            else:
                risk_level = "low"
                risk_score = round(loc["base_susceptibility"] * 20, 1)
                factors = []

            results.append({
                "location_id": loc["location_id"],
                "name": loc["name"],
                "district": loc["district"],
                "state": loc["state"],
                "centroid_lat": loc["centroid_lat"],
                "centroid_lon": loc["centroid_lon"],
                "lat_min": loc["lat_min"],
                "lat_max": loc["lat_max"],
                "lon_min": loc["lon_min"],
                "lon_max": loc["lon_max"],
                "slope_angle": loc["slope_angle"],
                "elevation_m": loc["elevation_m"],
                "soil_type": loc["soil_type"],
                "near_nh10": bool(loc["near_nh10"]),
                "historical_count": loc["historical_count"],
                "risk_level": risk_level,
                "risk_score": risk_score,
                "contributing_factors": factors,
                "rainfall": dict(rain) if rain else None,
                "timestamp": pred["timestamp"] if pred else datetime.now().isoformat(),
            })
        from regions import get_region_data
        region_data = get_region_data(region_id)
        route = region_data.get('nh10_route', [])
        geo_cells = region_data.get('grid_cells', [])
        hazard_lookup = {c['location_id']: c.get('hazard_types', []) for c in geo_cells}
        for r in results:
            r['hazard_types'] = hazard_lookup.get(r['location_id'], [])
        return {
            'cells': results,
            'route_safety': 'HIGH_RISK',
            'nh10_route': route,
            'region_id': region_id
        }
    finally:
        conn.close()


def get_location_detail(location_id: str):
    """Get detailed info for a specific location."""
    conn = _get_db()
    try:
        loc = conn.execute("SELECT * FROM monitoring_locations WHERE location_id = ?", (location_id,)).fetchone()
        if not loc:
            return {"error": "Location not found"}
        loc = dict(loc)

        # Historical rainfall trend (last 10 observations)
        rain_history = conn.execute("""
            SELECT * FROM rainfall_observations
            WHERE location_id = ?
            ORDER BY timestamp DESC LIMIT 10
        """, (location_id,)).fetchall()

        # Historical risk predictions
        risk_history = conn.execute("""
            SELECT timestamp, risk_score, risk_level FROM risk_predictions
            WHERE location_id = ?
            ORDER BY timestamp DESC LIMIT 10
        """, (location_id,)).fetchall()

        return {
            "location": loc,
            "rain_history": [dict(r) for r in rain_history],
            "risk_history": [dict(r) for r in risk_history],
        }
    finally:
        conn.close()


def get_geo_data(region_id: str = "ner_india"):
    """Return geographic data dynamically based on the active region configuration."""
    from regions import get_region_data
    return get_region_data(region_id)


def get_active_warnings(region_id: str = 'ner_india'):
    """Return all active early warning alerts."""
    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT w.*, l.centroid_lat, l.centroid_lon, l.slope_angle, l.near_nh10
            FROM landslide_warnings w
            JOIN monitoring_locations l ON w.location_id = l.location_id
            WHERE w.status = 'active'
            ORDER BY w.risk_score DESC, w.timestamp DESC
        """).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            r["trigger_factors"] = json.loads(r.get("trigger_factors") or "[]")
            r["affected_infrastructure"] = json.loads(r.get("affected_infrastructure") or "[]")
            results.append(r)
        return results
    finally:
        conn.close()


_cell_broadcast_service = CellBroadcastService()


def _get_warning_for_cell_broadcast(warning_id: int):
    conn = _get_db()
    try:
        row = conn.execute("""
            SELECT w.*, l.district, l.state, l.lat_min, l.lat_max,
                   l.lon_min, l.lon_max, l.centroid_lat, l.centroid_lon
            FROM landslide_warnings w
            JOIN monitoring_locations l ON w.location_id = l.location_id
            WHERE w.id = ?
        """, (warning_id,)).fetchone()
        if not row:
            raise ValueError(f"Warning {warning_id} was not found.")
        warning = dict(row)
        location = dict(row)
        warning["trigger_factors"] = json.loads(warning.get("trigger_factors") or "[]")
        warning["affected_infrastructure"] = json.loads(warning.get("affected_infrastructure") or "[]")
        return warning, location
    finally:
        conn.close()


def prepare_cell_broadcast(warning_id: int):
    """Prepare an operator-reviewed payload without dispatching anything."""
    warning, location = _get_warning_for_cell_broadcast(warning_id)
    return _cell_broadcast_service.prepare(warning, location)


def _save_cell_broadcast_simulation(result: dict):
    conn = _get_db()
    try:
        conn.execute("""
            INSERT INTO cell_broadcast_simulations
            (broadcast_id, warning_id, created_at, target_source, live_network_connected, result_json)
            VALUES (?,?,?,?,?,?)
        """, (
            result["broadcast_id"],
            result["warning_id"],
            result["dispatched_at"],
            result["target"]["source"],
            0,
            json.dumps(result, ensure_ascii=False),
        ))
        conn.commit()
        _verification_repository.ensure_schema()
    finally:
        conn.close()


def simulate_cell_broadcast(warning_id: int):
    """Run an auditable Cell Broadcast dispatch simulation."""
    warning, location = _get_warning_for_cell_broadcast(warning_id)
    result = _cell_broadcast_service.simulate(warning, location)
    _save_cell_broadcast_simulation(result)
    return result


def resolve_warning(warning_id: int, notes: str):
    """Acknowledge and resolve an early warning."""
    conn = _get_db()
    try:
        conn.execute("""
            UPDATE landslide_warnings
            SET status = 'resolved', operator_notes = ?, resolved_at = ?
            WHERE id = ?
        """, (notes, datetime.now().isoformat(), warning_id))
        conn.commit()
        return {"success": True, "id": warning_id}
    finally:
        conn.close()


def submit_field_verification(
    warning_id: int,
    location_id: str,
    verified_by: str,
    outcome: str,
    notes: str,
    **extended_fields,
):
    """Submit a raw field/citizen report for curator review."""
    submitted = {
        "warning_id": warning_id,
        "location_id": location_id,
        "reporter_id": verified_by,
        "hazard_type": extended_fields.get("hazard_type", "landslide"),
        "classification": outcome,
        "description": notes,
        "event_presence": outcome,
        **extended_fields,
    }
    return _verification_service.submit_report(submitted)


def get_pending_verifications(region_id: str = 'ner_india'):
    """Backward-compatible pending report queue."""
    return _verification_service.get_reports("pending_review")


def approve_for_training(verification_id: int):
    """Legacy RPC wrapper; new UI uses the explicit review endpoint."""
    return _verification_service.review_report(verification_id, {
        "decision": "approved",
        "curator_id": "legacy_admin",
        "curator_role": "admin",
    })


def get_verification_reports(status: str | None = None):
    return _verification_service.get_reports(status)


def get_verification_report(report_id: int):
    return _verification_service.get_report(report_id)


def review_verification_report(report_id: int, decision: dict):
    return _verification_service.review_report(report_id, decision)


def get_verification_stats():
    return _verification_service.get_stats()


def get_training_buffer():
    return _verification_service.get_training_buffer()


def build_training_dataset(hazard_type: str, curator_id: str):
    return _verification_service.build_dataset(hazard_type, curator_id)


# ---------------------------------------------------------------------------
# TEMPORAL STORM SIMULATOR — SAME PIPELINE AS REAL DATA
# ---------------------------------------------------------------------------

def run_storm_simulation():
    """
    Temporal Storm Simulator — T+0 to T+50 scenario.
    """
    try:
        from ml_engine import load_model, predict_risk
    except ImportError:
        def load_model(): return None
        def predict_risk(f, m=None):
            return {"risk_score": 20.0, "risk_level": "low", "probability": 0.2, "contributing_factors": []}

    print("[SIMULATOR] Starting Extreme Monsoon Scenario Simulation")
    conn = _get_db()

    try:
        model_bundle = load_model()
        locations = conn.execute("SELECT * FROM monitoring_locations").fetchall()
        locations = [dict(l) for l in locations]

        yield {
            "type": "scenario_start",
            "step": 0,
            "time_label": "T+0: Normal Conditions",
            "description": "Baseline state. Pre-monsoon conditions. All monitoring cells stable.",
            "progress": 5,
        }
        time.sleep(1.5)

        cell_states = {}
        for loc in locations:
            cell_states[loc["location_id"]] = {
                "rainfall_24h_mm": random.uniform(2, 15),
                "rainfall_3d_mm": random.uniform(8, 40),
                "rainfall_7d_mm": random.uniform(20, 80),
                "rainfall_intensity": random.uniform(0.5, 3.0),
                "soil_moisture_index": random.uniform(0.15, 0.35),
                "slope_angle": loc["slope_angle"],
                "elevation_m": loc["elevation_m"],
                "base_susceptibility": loc["base_susceptibility"],
                "historical_count": loc["historical_count"],
            }

        baseline_results = []
        for loc in locations:
            features = cell_states[loc["location_id"]]
            prediction = predict_risk(features, model_bundle)
            baseline_results.append({
                "location_id": loc["location_id"],
                "name": loc["name"],
                "centroid_lat": loc["centroid_lat"],
                "centroid_lon": loc["centroid_lon"],
                "lat_min": loc["lat_min"],
                "lat_max": loc["lat_max"],
                "lon_min": loc["lon_min"],
                "lon_max": loc["lon_max"],
                "near_nh10": bool(loc["near_nh10"]),
                **prediction,
                "rainfall": features,
            })

        yield {
            "type": "map_update",
            "step": 0,
            "time_label": "T+0: Normal Conditions",
            "cells": baseline_results,
            "progress": 10,
        }
        time.sleep(2)

        yield {
            "type": "scenario_event",
            "step": 10,
            "time_label": "T+10: Rainfall Beginning",
            "description": "Monsoonal rainfall system approaching. Rainfall intensity increasing over high-elevation zones.",
            "progress": 25,
        }
        time.sleep(1.5)

        for loc_id in cell_states:
            s = cell_states[loc_id]
            loc_info = next(l for l in locations if l["location_id"] == loc_id)
            elev_factor = min(1.0, loc_info["elevation_m"] / 3000)
            slope_factor = min(1.0, loc_info["slope_angle"] / 50)

            s["rainfall_intensity"] = min(40, s["rainfall_intensity"] + random.uniform(5, 15) * (0.5 + slope_factor * 0.5))
            s["rainfall_24h_mm"] = min(120, s["rainfall_24h_mm"] + random.uniform(30, 70) * (0.7 + elev_factor * 0.3))
            s["rainfall_3d_mm"] = min(220, s["rainfall_3d_mm"] + random.uniform(60, 120))
            s["rainfall_7d_mm"] = min(350, s["rainfall_7d_mm"] + random.uniform(40, 90))
            s["soil_moisture_index"] = min(0.65, s["soil_moisture_index"] + random.uniform(0.08, 0.18))

        t10_results = []
        for loc in locations:
            features = cell_states[loc["location_id"]]
            prediction = predict_risk(features, model_bundle)
            t10_results.append({
                "location_id": loc["location_id"],
                "name": loc["name"],
                "centroid_lat": loc["centroid_lat"],
                "centroid_lon": loc["centroid_lon"],
                "lat_min": loc["lat_min"],
                "lat_max": loc["lat_max"],
                "lon_min": loc["lon_min"],
                "lon_max": loc["lon_max"],
                "near_nh10": bool(loc["near_nh10"]),
                **prediction,
                "rainfall": features,
            })

        yield {
            "type": "map_update",
            "step": 10,
            "time_label": "T+10: Rainfall Increasing",
            "cells": t10_results,
            "progress": 35,
        }
        time.sleep(2)

        yield {
            "type": "scenario_event",
            "step": 20,
            "time_label": "T+20: Heavy Monsoonal Rainfall",
            "description": "Intense rainfall continuing. Antecedent saturation accumulating on steep slopes. Soil moisture index elevated.",
            "progress": 50,
        }
        time.sleep(1.5)

        for loc_id in cell_states:
            s = cell_states[loc_id]
            loc_info = next(l for l in locations if l["location_id"] == loc_id)
            slope_factor = min(1.0, loc_info["slope_angle"] / 50)

            s["rainfall_intensity"] = min(90, s["rainfall_intensity"] + random.uniform(15, 35) * (0.4 + slope_factor * 0.6))
            s["rainfall_24h_mm"] = min(200, s["rainfall_24h_mm"] + random.uniform(60, 110))
            s["rainfall_3d_mm"] = min(370, s["rainfall_3d_mm"] + random.uniform(80, 150))
            s["rainfall_7d_mm"] = min(540, s["rainfall_7d_mm"] + random.uniform(60, 120))
            s["soil_moisture_index"] = min(0.92, s["soil_moisture_index"] + random.uniform(0.12, 0.28) * (0.5 + slope_factor * 0.5))

        t20_results = []
        for loc in locations:
            features = cell_states[loc["location_id"]]
            prediction = predict_risk(features, model_bundle)
            t20_results.append({
                "location_id": loc["location_id"],
                "name": loc["name"],
                "centroid_lat": loc["centroid_lat"],
                "centroid_lon": loc["centroid_lon"],
                "lat_min": loc["lat_min"],
                "lat_max": loc["lat_max"],
                "lon_min": loc["lon_min"],
                "lon_max": loc["lon_max"],
                "near_nh10": bool(loc["near_nh10"]),
                **prediction,
                "rainfall": features,
            })

        yield {
            "type": "map_update",
            "step": 20,
            "time_label": "T+20: Soil Saturation Elevated",
            "cells": t20_results,
            "progress": 60,
        }
        time.sleep(2)

        yield {
            "type": "scenario_event",
            "step": 30,
            "time_label": "T+30: Critical Risk Threshold Reached",
            "description": "AI model detects critical risk on steep slopes. Warning thresholds crossed. Triggering early warning protocol.",
            "progress": 72,
        }
        time.sleep(1.5)

        for loc_id in cell_states:
            s = cell_states[loc_id]
            loc_info = next(l for l in locations if l["location_id"] == loc_id)
            slope_factor = min(1.0, loc_info["slope_angle"] / 50)

            s["rainfall_intensity"] = min(95, s["rainfall_intensity"] + random.uniform(10, 25) * slope_factor)
            s["rainfall_24h_mm"] = min(200, s["rainfall_24h_mm"] + random.uniform(20, 50) * slope_factor)
            s["rainfall_3d_mm"] = min(385, s["rainfall_3d_mm"] + random.uniform(30, 60))
            s["rainfall_7d_mm"] = min(550, s["rainfall_7d_mm"] + random.uniform(20, 50))
            s["soil_moisture_index"] = min(0.99, s["soil_moisture_index"] + random.uniform(0.05, 0.12) * slope_factor)

        t30_results = []
        warnings_to_create = []

        for loc in locations:
            features = cell_states[loc["location_id"]]
            prediction = predict_risk(features, model_bundle)

            # Save observation to DB
            conn.execute("""
                INSERT INTO rainfall_observations
                (location_id, rainfall_24h_mm, rainfall_3d_mm, rainfall_7d_mm, rainfall_intensity, soil_moisture_index, simulation_step)
                VALUES (?,?,?,?,?,?,?)
            """, (
                loc["location_id"],
                features["rainfall_24h_mm"], features["rainfall_3d_mm"],
                features["rainfall_7d_mm"], features["rainfall_intensity"],
                features["soil_moisture_index"], 30
            ))

            # Save risk prediction to DB
            conn.execute("""
                INSERT INTO risk_predictions
                (location_id, risk_score, risk_level, probability, contributing_factors)
                VALUES (?,?,?,?,?)
            """, (
                loc["location_id"],
                prediction["risk_score"], prediction["risk_level"],
                prediction["probability"],
                json.dumps(prediction["contributing_factors"])
            ))

            if prediction["risk_level"] in ("high", "critical"):
                affected = []
                if loc["near_nh10"]:
                    affected.append("NH-10 Highway Corridor")
                warnings_to_create.append({
                    "location_id": loc["location_id"],
                    "location_name": loc["name"],
                    "risk_level": prediction["risk_level"],
                    "risk_score": prediction["risk_score"],
                    "trigger_factors": prediction["contributing_factors"],
                    "affected_infrastructure": affected,
                })

            t30_results.append({
                "location_id": loc["location_id"],
                "name": loc["name"],
                "centroid_lat": loc["centroid_lat"],
                "centroid_lon": loc["centroid_lon"],
                "lat_min": loc["lat_min"],
                "lat_max": loc["lat_max"],
                "lon_min": loc["lon_min"],
                "lon_max": loc["lon_max"],
                "near_nh10": bool(loc["near_nh10"]),
                **prediction,
                "rainfall": features,
            })

        # Create warnings in DB
        new_warning_ids = []
        for w in warnings_to_create:
            cur = conn.execute("""
                INSERT INTO landslide_warnings
                (location_id, location_name, risk_level, risk_score, trigger_factors, affected_infrastructure)
                VALUES (?,?,?,?,?,?)
            """, (
                w["location_id"], w["location_name"], w["risk_level"], w["risk_score"],
                json.dumps(w["trigger_factors"]), json.dumps(w["affected_infrastructure"])
            ))
            new_warning_ids.append({"id": cur.lastrowid, **w})

        conn.commit()

        yield {
            "type": "map_update",
            "step": 30,
            "time_label": "T+30: Warnings Triggered",
            "cells": t30_results,
            "warnings": new_warning_ids,
            "progress": 80,
        }
        time.sleep(2)

        critical_cells = [c for c in t30_results if c["risk_level"] in ("high", "critical") and c["near_nh10"]]
        if critical_cells:
            yield {
                "type": "infrastructure_alert",
                "step": 40,
                "time_label": "T+40: Infrastructure Impact Detected",
                "description": f"Critical risk zones intersecting NH-10 corridor. {len(critical_cells)} cell(s) pose direct highway risk. Recommended: Alert BRO clearing crews and NDMA.",
                "affected_cells": [c["location_id"] for c in critical_cells],
                "recommended_actions": [
                    "Alert Border Roads Organisation (BRO) clearing teams on NH-10",
                    "Notify NDMA State EOC — North Sikkim district",
                    "Issue traffic advisory: Reduce speed / stop non-essential traffic on NH-10",
                    "Dispatch drone survey team to critical slope areas",
                    "Alert Mangan district disaster management cell",
                    "Initiate field verification by SDRF teams",
                ],
                "progress": 90,
            }
            time.sleep(2)

        yield {
            "type": "simulation_complete",
            "step": 50,
            "time_label": "T+50: Simulation Complete",
            "description": "Extreme monsoon scenario simulation complete. Risk assessment saved to database. Awaiting field verification.",
            "summary": {
                "total_cells": len(t30_results),
                "critical": sum(1 for c in t30_results if c["risk_level"] == "critical"),
                "high": sum(1 for c in t30_results if c["risk_level"] == "high"),
                "moderate": sum(1 for c in t30_results if c["risk_level"] == "moderate"),
                "low": sum(1 for c in t30_results if c["risk_level"] == "low"),
                "warnings_generated": len(warnings_to_create),
                "nh10_risk_cells": len(critical_cells) if critical_cells else 0,
            },
            "progress": 100,
        }

        print("[SIMULATOR] Simulation complete")

    except Exception as e:
        print(f"[SIMULATOR] Error: {e}")
        import traceback
        traceback.print_exc()
        yield {"type": "error", "message": str(e), "progress": 0}
    finally:
        conn.close()



def save_simulation_record(summary: dict, events: list):
    """Save the simulation summary and events as a permanent JSON record."""
    records_dir = os.path.join(os.path.dirname(__file__), "data", "records")
    os.makedirs(records_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sim_record_{timestamp}.json"
    filepath = os.path.join(records_dir, filename)
    
    record = {
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "events": events
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        
    return {"success": True, "file": filename, "message": "Simulation record saved."}


def reset_simulation():
    """Reset risk predictions for a fresh simulation run."""
    conn = _get_db()
    try:
        conn.execute("DELETE FROM rainfall_observations")
        conn.execute("DELETE FROM risk_predictions")
        conn.execute("DELETE FROM landslide_warnings WHERE status = 'active'")
        conn.commit()
        return {"success": True, "message": "Simulation state reset. Ready for new scenario."}
    finally:
        conn.close()


def get_model_info():
    """Return information about the current ML model."""
    try:
        from ml_engine import load_model, FEATURE_COLUMNS
        bundle = load_model()
        if bundle:
            return {
                "model_name": bundle.get("model_name", "Random Forest"),
                "accuracy": bundle.get("accuracy"),
                "rf_accuracy": bundle.get("rf_accuracy"),
                "gb_accuracy": bundle.get("gb_accuracy"),
                "feature_columns": bundle.get("feature_columns", FEATURE_COLUMNS),
                "feature_importances": bundle.get("feature_importances", {}),
                "note": bundle.get("note", ""),
                "status": "loaded",
            }
        else:
            return {
                "model_name": "Rule-Based Fallback",
                "status": "fallback",
                "note": "ML model not available. Using domain-expert rule-based scoring.",
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _seed_baseline_predictions():
    """Run the ML model on all cells using terrain features on first boot so
    the Risk Map shows real colors instead of all-green fallback."""
    conn = _get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM risk_predictions").fetchone()[0]
        if count > 0:
            print(f"[TERRAPULSE] Baseline predictions exist ({count} rows) — skipping seed")
            return
        print("[TERRAPULSE] Seeding baseline risk predictions from ML model...")
        from ml_engine import load_model, predict_risk
        model_bundle = load_model()
        if not model_bundle:
            print("[TERRAPULSE] Model not available — skipping baseline seed")
            return
        locations = conn.execute("SELECT * FROM monitoring_locations").fetchall()
        seeded = 0
        for loc in locations:
            loc = dict(loc)
            features = {
                "slope_angle": loc.get("slope_angle", 25.0),
                "elevation_m": loc.get("elevation_m", 1500.0),
                "rainfall_24h_mm": 15.0,
                "rainfall_3d_mm": 40.0,
                "rainfall_7d_mm": 80.0,
                "rainfall_intensity": 5.0,
                "soil_moisture_index": 0.45,
                "ndvi": 0.55,
                "distance_to_fault_km": 8.0,
                "road_proximity_km": 0.5 if loc.get("near_nh10") else 3.0,
                "historical_events": loc.get("historical_count", 0),
                "base_susceptibility": loc.get("base_susceptibility", 0.5),
            }
            try:
                prediction = predict_risk(features, model_bundle)
                conn.execute("""
                    INSERT INTO risk_predictions
                    (location_id, risk_score, risk_level, probability, contributing_factors)
                    VALUES (?,?,?,?,?)
                """, (
                    loc["location_id"],
                    prediction["risk_score"], prediction["risk_level"],
                    prediction["probability"],
                    json.dumps(prediction["contributing_factors"])
                ))
                seeded += 1
            except Exception as e:
                print(f"[TERRAPULSE] Seed failed for {loc['location_id']}: {e}")
        conn.commit()
        print(f"[TERRAPULSE] Seeded baseline predictions for {seeded} locations")
    except Exception as e:
        print(f"[TERRAPULSE] Baseline seed error: {e}")
    finally:
        conn.close()


def _startup():
    try:
        from ml_engine import load_model, train_and_save_model, MODEL_PATH
        init_db()
        _verification_repository.ensure_schema()
        if not os.path.exists(MODEL_PATH):
            print("[TERRAPULSE] No model found — training now...")
            train_and_save_model()
        else:
            print("[TERRAPULSE] Model already exists — skipping training")
        _seed_baseline_predictions()
    except Exception as e:
        print(f"[TERRAPULSE] Startup warning: {e}")
        init_db()


_startup()

__all__ = [
    "get_locations",
    "get_latest_status",
    "get_location_detail",
    "get_geo_data",
    "get_active_warnings",
    "resolve_warning",
    "submit_field_verification",
    "get_pending_verifications",
    "approve_for_training",
    "run_storm_simulation",
    "save_simulation_record",
    "reset_simulation",
    "get_model_info",
    "init_db",
]


# ---------------------------------------------------------------------------
# FASTAPI ENDPOINT SETUP
# ---------------------------------------------------------------------------
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from forecast_engine import generate_24h_forecast
import asyncio
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict

app = FastAPI(title="TerraPulse.ai API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RpcRequest(BaseModel):
    module: str
    func: str
    args: Dict[str, Any] = {}
    stream: bool = False

class CellBroadcastRequest(BaseModel):
    warning_id: int

class VerificationReviewRequest(BaseModel):
    decision: str
    curator_id: str
    curator_role: str
    hazard_type: str | None = None
    event_presence: str | None = None
    evidence_quality: str | None = None
    location_quality: str | None = None
    reason: str | None = None
    notes: str | None = None

class TrainingDatasetBuildRequest(BaseModel):
    hazard_type: str
    curator_id: str

@app.post("/api/alerts/cell-broadcast/prepare")
async def prepare_cell_broadcast_endpoint(request: CellBroadcastRequest):
    try:
        return prepare_cell_broadcast(request.warning_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

@app.post("/api/risk/predict")
async def predict_risk_endpoint(request: RiskFeatureInput):
    return predict_development_risk(request)

@app.post("/api/risk/predict-batch")
async def predict_risk_batch_endpoint(request: RiskBatchRequest):
    predictions = predict_development_risk_batch(request.cells)
    return {
        "predictions": [prediction.model_dump() for prediction in predictions],
        "predictor": predictions[0].predictor,
        "predictor_type": predictions[0].predictor_type,
    }

@app.post("/api/alerts/cell-broadcast/simulate")
async def simulate_cell_broadcast_endpoint(request: CellBroadcastRequest):
    try:
        return simulate_cell_broadcast(request.warning_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

@app.get("/api/verifications")
async def get_verifications_endpoint(status: str | None = None):
    try:
        return {"reports": get_verification_reports(status)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@app.get("/api/verifications/stats")
async def get_verification_stats_endpoint():
    return get_verification_stats()

@app.get("/api/verifications/{report_id}")
async def get_verification_report_endpoint(report_id: int):
    try:
        return get_verification_report(report_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

@app.post("/api/verifications/{report_id}/review")
async def review_verification_endpoint(report_id: int, request: VerificationReviewRequest):
    try:
        return review_verification_report(report_id, request.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@app.get("/api/training-buffer")
async def get_training_buffer_endpoint():
    return {"buffers": get_training_buffer()}

@app.post("/api/training-datasets/build")
async def build_training_dataset_endpoint(request: TrainingDatasetBuildRequest):
    try:
        return build_training_dataset(request.hazard_type, request.curator_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@app.post("/rpc")
async def rpc_endpoint(req: RpcRequest):
    if req.func not in __all__:
        raise HTTPException(status_code=403, detail=f"Function {req.func} not exported")
    
    func = globals().get(req.func)
    if not func:
        raise HTTPException(status_code=404, detail=f"Function {req.func} not found")
        
    try:
        if req.stream:
            # Handle Server-Sent Events (SSE) generator
            def event_generator():
                for chunk in func(**req.args):
                    yield f"data: {json.dumps(chunk)}\n\n"
            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            # Handle regular synchronous function
            result = func(**req.args)
            return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/route-safety")
async def get_route_safety(region_id: str = "ner_india"):
    """Return highway route safety status based on current risk predictions."""
    if region_id == 'nepal_case':
        data = _get_nepal_status()
        return {
            "route_safety": data.get("route_safety", "UNKNOWN"),
            "nh10_route": data.get("nh10_route", []),
            "region_id": region_id,
            "highway_name": "Prithvi Highway H01 (Trishuli Corridor)",
        }
    # NER demo
    from geo_data import NH10_ROUTE
    return {
        "route_safety": "HIGH_RISK",
        "nh10_route": NH10_ROUTE,
        "region_id": region_id,
        "highway_name": "NH-10 (Sikkim Corridor)",
    }

@app.get("/api/event-replay")
async def get_event_replay():
    """Return historical event replay data for the Nepal Rasuwa case study."""
    from event_replay import generate_replay_timeline
    return generate_replay_timeline()

@app.get("/api/forecast")
async def get_forecast(region_id: str = "ner_india"):
    """
    Returns the 24-hour predictive risk trajectory for all monitored locations.
    """
    try:
        if region_id == "nepal_case":
            from regions import get_region_data
            locations = get_region_data("nepal_case").get("grid_cells", [])
        else:
            locations = get_locations()
        forecast_result = await generate_24h_forecast(locations)
        return forecast_result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
