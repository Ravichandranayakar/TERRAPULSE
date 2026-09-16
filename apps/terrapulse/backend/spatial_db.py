"""
Stage 07 - Spatial database layer (PostGIS).

PostgreSQL 16 + PostGIS 3.6 is what the risk output is stored in, so the map can
answer spatial questions in the database instead of in Python:

    - which cells lie within 25 km of a reported landslide
    - which cells intersect the NH-10 corridor
    - which cells are inside a district polygon

That is the reason to use PostGIS at all. Storing a latitude and longitude in a
normal table would not let us ask any of those.

Connection
  TERRAPULSE_PG_DSN, default postgresql://postgres@127.0.0.1:5433/terrapulse
  PostGIS runs on a second cluster on port 5433; the machine's 5432 service is
  left untouched.

Failure behaviour
  Every entry point is safe to call when PostGIS is not running. It reports
  available=False and the reason. The pipeline continues on SQLite, because a
  missing spatial database must not stop the risk map.
"""

import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DSN_ENV = "TERRAPULSE_PG_DSN"
DEFAULT_DSN = "postgresql://postgres@127.0.0.1:5433/terrapulse"

SRID = 4326
# Local azimuthal equidistant projection, matching the distance extraction, so
# "within N metres" means true metres rather than degrees.
AEQD_SRID = 3857


def dsn() -> str:
    return os.environ.get(DSN_ENV) or DEFAULT_DSN


def connect():
    import psycopg2
    conn = psycopg2.connect(dsn(), connect_timeout=5)
    conn.autocommit = True
    return conn


def status() -> Dict[str, Any]:
    """Whether the spatial database is reachable and has PostGIS."""
    try:
        conn = connect()
    except Exception as error:
        return {"available": False, "reason": str(error), "dsn": dsn()}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT PostGIS_Version(), version();")
            postgis_version, pg_version = cur.fetchone()
        return {
            "available": True,
            "dsn": dsn(),
            "postgis_version": postgis_version,
            "postgres_version": pg_version.split(" on ")[0],
        }
    finally:
        conn.close()


DDL = """
CREATE TABLE IF NOT EXISTS monitoring_cells (
    location_id     TEXT PRIMARY KEY,
    name            TEXT,
    district        TEXT,
    state           TEXT,
    centroid        geometry(Point, 4326),
    footprint       geometry(Polygon, 4326),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS monitoring_cells_centroid_idx
    ON monitoring_cells USING GIST (centroid);
CREATE INDEX IF NOT EXISTS monitoring_cells_footprint_idx
    ON monitoring_cells USING GIST (footprint);

CREATE TABLE IF NOT EXISTS risk_observations (
    id                  BIGSERIAL PRIMARY KEY,
    location_id         TEXT NOT NULL REFERENCES monitoring_cells(location_id),
    observed_at         TIMESTAMPTZ NOT NULL,
    susceptibility      REAL,
    susceptibility_class TEXT,
    rainfall_24h_mm     REAL,
    rainfall_7d_mm      REAL,
    soil_moisture       REAL,
    trigger_level       TEXT,
    alert_level         TEXT,
    model_version       TEXT,
    live_data           BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS risk_observations_lookup_idx
    ON risk_observations (location_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS historical_landslides (
    slide_id    TEXT PRIMARY KEY,
    event_date  DATE,
    hazard_type TEXT,
    geom        geometry(Point, 4326)
);
CREATE INDEX IF NOT EXISTS historical_landslides_geom_idx
    ON historical_landslides USING GIST (geom);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           BIGSERIAL PRIMARY KEY,
    started_at   TIMESTAMPTZ DEFAULT now(),
    stages       JSONB,
    model_version TEXT,
    cells_scored INTEGER,
    notes        TEXT
);
"""


def ensure_schema() -> Dict[str, Any]:
    try:
        conn = connect()
    except Exception as error:
        return {"available": False, "reason": str(error)}
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        return {"available": True, "schema": "ready"}
    finally:
        conn.close()


def upsert_cells(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Write monitoring cells with real point + polygon geometry."""
    try:
        conn = connect()
    except Exception as error:
        return {"available": False, "written": 0, "reason": str(error)}
    try:
        written = 0
        with conn.cursor() as cur:
            for cell in cells:
                lat = cell.get("centroid_lat")
                lon = cell.get("centroid_lon")
                if lat is None or lon is None:
                    continue
                lat_min, lat_max = cell.get("lat_min"), cell.get("lat_max")
                lon_min, lon_max = cell.get("lon_min"), cell.get("lon_max")
                footprint = None
                if None not in (lat_min, lat_max, lon_min, lon_max):
                    footprint = (
                        "SRID=%d;POLYGON((%f %f,%f %f,%f %f,%f %f,%f %f))" % (
                            SRID, lon_min, lat_min, lon_max, lat_min,
                            lon_max, lat_max, lon_min, lat_max,
                            lon_min, lat_min)
                    )
                cur.execute("""
                    INSERT INTO monitoring_cells
                        (location_id, name, district, state, centroid, footprint, updated_at)
                    VALUES (%s, %s, %s, %s,
                            ST_SetSRID(ST_MakePoint(%s, %s), %s),
                            CASE WHEN %s IS NULL THEN NULL
                                 ELSE ST_GeomFromEWKT(%s) END,
                            now())
                    ON CONFLICT (location_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        district = EXCLUDED.district,
                        state = EXCLUDED.state,
                        centroid = EXCLUDED.centroid,
                        footprint = EXCLUDED.footprint,
                        updated_at = now()
                """, (cell.get("location_id"), cell.get("name"), cell.get("district"),
                      cell.get("state"), lon, lat, SRID,
                      footprint, footprint))
                written += 1
        return {"available": True, "written": written}
    finally:
        conn.close()


def write_cycle(payload: Dict[str, Any], model_version: Optional[str] = None) -> Dict[str, Any]:
    """Persist one live cycle's risk output."""
    try:
        conn = connect()
    except Exception as error:
        return {"available": False, "written": 0, "reason": str(error)}
    try:
        written = 0
        observed_at = payload.get("generated_at") or datetime.now(timezone.utc).isoformat()
        with conn.cursor() as cur:
            for cell in payload.get("cells", []):
                cond = cell.get("conditions") or {}
                cur.execute("""
                    INSERT INTO risk_observations
                        (location_id, observed_at, susceptibility, susceptibility_class,
                         rainfall_24h_mm, rainfall_7d_mm, soil_moisture,
                         trigger_level, alert_level, model_version, live_data)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    cell["location_id"], observed_at,
                    cell.get("susceptibility_score"), cell.get("susceptibility_class"),
                    cond.get("rainfall_24h_mm"), cond.get("rainfall_7d_mm"),
                    cond.get("soil_moisture_0_to_7cm"),
                    (cell.get("trigger") or {}).get("level"),
                    (cell.get("alert") or {}).get("alert_level"),
                    model_version, bool(cond.get("available")),
                ))
                written += 1
        return {"available": True, "written": written, "observed_at": observed_at}
    finally:
        conn.close()


def upsert_historical_landslides(landslides: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        conn = connect()
    except Exception as error:
        return {"available": False, "written": 0, "reason": str(error)}
    try:
        written = 0
        with conn.cursor() as cur:
            for slide in landslides:
                lat, lon = slide.get("lat"), slide.get("lon")
                if lat is None or lon is None:
                    continue
                cur.execute("""
                    INSERT INTO historical_landslides (slide_id, event_date, hazard_type, geom)
                    VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), %s))
                    ON CONFLICT (slide_id) DO UPDATE SET
                        event_date = EXCLUDED.event_date,
                        hazard_type = EXCLUDED.hazard_type,
                        geom = EXCLUDED.geom
                """, (slide.get("id"), slide.get("date"), slide.get("type"),
                      lon, lat, SRID))
                written += 1
        return {"available": True, "written": written}
    finally:
        conn.close()


def cells_within_metres_of_landslides(metres: float = 25000.0, limit: int = 50) -> Dict[str, Any]:
    """Cells within a true-metre radius of any recorded landslide.

    This is the query PostGIS exists for: geometry in the database rather than
    a Python loop over coordinates.
    """
    try:
        conn = connect()
    except Exception as error:
        return {"available": False, "reason": str(error), "results": []}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.location_id, c.name,
                       MIN(ST_Distance(
                             ST_Transform(c.centroid, 3857),
                             ST_Transform(l.geom, 3857))) AS distance_m
                FROM monitoring_cells c
                JOIN historical_landslides l
                  ON ST_DWithin(ST_Transform(c.centroid, 3857),
                                ST_Transform(l.geom, 3857), %s)
                GROUP BY c.location_id, c.name
                ORDER BY distance_m
                LIMIT %s
            """, (metres, limit))
            rows = cur.fetchall()
        return {"available": True, "radius_m": metres,
                "results": [{"location_id": r[0], "name": r[1],
                             "distance_m": round(float(r[2]), 1)} for r in rows]}
    finally:
        conn.close()


def latest_risk_per_cell() -> Dict[str, Any]:
    try:
        conn = connect()
    except Exception as error:
        return {"available": False, "reason": str(error), "results": []}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (location_id)
                       location_id, observed_at, susceptibility, susceptibility_class,
                       rainfall_24h_mm, trigger_level, alert_level
                FROM risk_observations
                ORDER BY location_id, observed_at DESC
            """)
            rows = cur.fetchall()
        return {"available": True, "results": [{
            "location_id": r[0], "observed_at": r[1].isoformat() if r[1] else None,
            "susceptibility": r[2], "susceptibility_class": r[3],
            "rainfall_24h_mm": r[4], "trigger_level": r[5], "alert_level": r[6],
        } for r in rows]}
    finally:
        conn.close()


def record_pipeline_run(stages: List[Dict[str, Any]], model_version: Optional[str],
                        cells_scored: int, notes: str = "") -> Dict[str, Any]:
    try:
        conn = connect()
    except Exception as error:
        return {"available": False, "reason": str(error)}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pipeline_runs (stages, model_version, cells_scored, notes)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (json.dumps(stages), model_version, cells_scored, notes))
            run_id = cur.fetchone()[0]
        return {"available": True, "run_id": run_id}
    finally:
        conn.close()