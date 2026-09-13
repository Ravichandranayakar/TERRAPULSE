import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator


VERIFICATION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("reporter_id", "TEXT"),
    ("reporter_role", "TEXT DEFAULT 'field_officer'"),
    ("observed_at", "TEXT"),
    ("latitude", "REAL"),
    ("longitude", "REAL"),
    ("geometry", "TEXT"),
    ("submitted_hazard_type", "TEXT"),
    ("hazard_type", "TEXT DEFAULT 'landslide'"),
    ("classification", "TEXT"),
    ("description", "TEXT"),
    ("severity", "TEXT"),
    ("photo_reference", "TEXT"),
    ("infrastructure_impact", "TEXT"),
    ("location_accuracy", "REAL"),
    ("source_type", "TEXT DEFAULT 'field_officer'"),
    ("source_reference", "TEXT"),
    ("status", "TEXT DEFAULT 'pending_review'"),
    ("curator_id", "TEXT"),
    ("curator_reviewed_at", "TEXT"),
    ("curator_notes", "TEXT"),
    ("rejection_reason", "TEXT"),
    ("training_eligibility", "TEXT DEFAULT 'not_eligible'"),
    ("dataset_version", "TEXT"),
    ("model_target", "TEXT"),
    ("event_presence", "TEXT"),
    ("location_quality", "TEXT"),
    ("temporal_quality", "TEXT"),
    ("evidence_quality", "TEXT"),
    ("duplicate_of", "INTEGER"),
    ("possible_duplicate_ids", "TEXT"),
    ("submitted_event_presence", "TEXT"),
)


class VerificationRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS field_verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    warning_id INTEGER,
                    location_id TEXT,
                    reported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    verified_by TEXT,
                    outcome TEXT,
                    field_notes TEXT,
                    is_approved_for_training INTEGER DEFAULT 0
                )
            """)
            existing = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(field_verifications)")
            }
            for name, definition in VERIFICATION_COLUMNS:
                if name not in existing:
                    conn.execute(f"ALTER TABLE field_verifications ADD COLUMN {name} {definition}")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    curator_id TEXT,
                    timestamp TEXT NOT NULL,
                    previous_status TEXT,
                    new_status TEXT,
                    notes TEXT,
                    FOREIGN KEY(report_id) REFERENCES field_verifications(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_version TEXT NOT NULL UNIQUE,
                    hazard_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    source_reports TEXT NOT NULL,
                    source_datasets TEXT NOT NULL,
                    feature_schema_version TEXT NOT NULL,
                    label_policy_version TEXT NOT NULL,
                    curator_version TEXT NOT NULL,
                    manifest_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_field_verifications_status
                ON field_verifications(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_field_verifications_hazard
                ON field_verifications(hazard_type, training_eligibility)
            """)
            self._backfill_legacy_rows(conn)
            conn.commit()

    def _backfill_legacy_rows(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            UPDATE field_verifications
            SET reporter_id = COALESCE(reporter_id, verified_by),
                reporter_role = COALESCE(reporter_role, 'field_officer'),
                description = COALESCE(description, field_notes),
                submitted_hazard_type = COALESCE(submitted_hazard_type, hazard_type),
                hazard_type = COALESCE(hazard_type, 'landslide'),
                source_type = COALESCE(source_type, 'field_officer'),
                status = COALESCE(status, CASE WHEN is_approved_for_training = 1 THEN 'approved' ELSE 'pending_review' END),
                training_eligibility = COALESCE(
                    training_eligibility,
                    CASE WHEN is_approved_for_training = 1 THEN 'eligible' ELSE 'not_eligible' END
                ),
                event_presence = COALESCE(event_presence, outcome),
                submitted_event_presence = COALESCE(submitted_event_presence, event_presence),
                observed_at = COALESCE(observed_at, reported_at)
            WHERE reporter_id IS NULL
               OR description IS NULL
               OR hazard_type IS NULL
               OR source_type IS NULL
               OR status IS NULL
               OR training_eligibility IS NULL
               OR event_presence IS NULL
               OR observed_at IS NULL
        """)
        conn.execute("""
            UPDATE field_verifications
            SET latitude = locations.centroid_lat,
                longitude = locations.centroid_lon,
                location_quality = COALESCE(location_quality, 'approximate'),
                model_target = COALESCE(model_target, 'landslide_model')
            FROM monitoring_locations AS locations
            WHERE field_verifications.location_id = locations.location_id
              AND field_verifications.latitude IS NULL
        """)

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        record = dict(row)
        for key in ("infrastructure_impact", "possible_duplicate_ids"):
            try:
                record[key] = json.loads(record.get(key) or "[]")
            except (TypeError, json.JSONDecodeError):
                record[key] = []
        return record

    def insert_report(self, report: dict[str, Any]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            cursor = conn.execute("""
                INSERT INTO field_verifications (
                    warning_id, location_id, reported_at, verified_by, outcome, field_notes,
                    is_approved_for_training, reporter_id, reporter_role, observed_at,
                    latitude, longitude, geometry, submitted_hazard_type, hazard_type,
                    classification, description,
                    severity, photo_reference, infrastructure_impact, location_accuracy,
                    source_type, source_reference, status, event_presence, location_quality,
                    temporal_quality, evidence_quality, duplicate_of, possible_duplicate_ids,
                    model_target, training_eligibility, submitted_event_presence
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                report.get("warning_id"), report.get("location_id"), now,
                report.get("reporter_id"), report.get("classification"),
                report.get("description"), 0, report.get("reporter_id"),
                report.get("reporter_role"), report.get("observed_at"),
                report.get("latitude"), report.get("longitude"),
                json.dumps(report["geometry"]) if report.get("geometry") else None,
                report.get("submitted_hazard_type", report["hazard_type"]),
                report["hazard_type"], report.get("classification"),
                report.get("description"), report.get("severity"),
                report.get("photo_reference"),
                json.dumps(report.get("infrastructure_impact") or []),
                report.get("location_accuracy"), report.get("source_type"),
                report.get("source_reference"), "pending_review",
                report.get("event_presence"), report.get("location_quality"),
                report.get("temporal_quality"), report.get("evidence_quality"),
                report.get("duplicate_of"),
                json.dumps(report.get("possible_duplicate_ids") or []),
                report["model_target"], "not_eligible",
                report.get("submitted_event_presence", report["event_presence"]),
            ))
            conn.commit()
            return int(cursor.lastrowid)

    def get_reports(self, status: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT fv.*, w.location_name, w.risk_level, w.risk_score
            FROM field_verifications fv
            LEFT JOIN landslide_warnings w ON fv.warning_id = w.id
        """
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE fv.status = ?"
            params = (status,)
        query += " ORDER BY fv.reported_at DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._decode_row(row) for row in rows]

    def get_report(self, report_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("""
                SELECT fv.*, w.location_name, w.risk_level, w.risk_score
                FROM field_verifications fv
                LEFT JOIN landslide_warnings w ON fv.warning_id = w.id
                WHERE fv.id = ?
            """, (report_id,)).fetchone()
            return self._decode_row(row) if row else None

    def get_location(self, location_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("""
                SELECT * FROM monitoring_locations WHERE location_id = ?
            """, (location_id,)).fetchone()
            return dict(row) if row else None

    def find_candidate_duplicates(
        self,
        report_id: int,
        hazard_type: str,
        latitude: float | None,
        longitude: float | None,
        observed_at: str | None,
    ) -> list[int]:
        if latitude is None or longitude is None or observed_at is None:
            return []
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT id, latitude, longitude, observed_at
                FROM field_verifications
                WHERE hazard_type = ? AND id != ? AND status != 'rejected'
                ORDER BY observed_at DESC LIMIT 500
            """, (hazard_type, report_id)).fetchall()
            candidates: list[int] = []
            for row in rows:
                if row["latitude"] is None or row["longitude"] is None or not row["observed_at"]:
                    continue
                try:
                    time_gap = abs(
                        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                        - datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
                    ).total_seconds()
                except ValueError:
                    continue
                spatial_gap = (
                    (float(row["latitude"]) - latitude) ** 2
                    + (float(row["longitude"]) - longitude) ** 2
                ) ** 0.5
                if time_gap <= 72 * 3600 and spatial_gap <= 0.005:
                    candidates.append(int(row["id"]))
            return candidates

    def update_review(self, report_id: int, fields: dict[str, Any]) -> None:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [report_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE field_verifications SET {assignments} WHERE id = ?", values)
            conn.commit()

    def insert_audit_event(self, event: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO verification_audit_events
                (report_id, action, curator_id, timestamp, previous_status, new_status, notes)
                VALUES (?,?,?,?,?,?,?)
            """, (
                event["report_id"], event["action"], event.get("curator_id"),
                event["timestamp"], event.get("previous_status"),
                event.get("new_status"), event.get("notes"),
            ))
            conn.commit()

    def get_audit_events(self, report_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM verification_audit_events
                WHERE report_id = ? ORDER BY timestamp DESC
            """, (report_id,)).fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> dict[str, int]:
        with self.connect() as conn:
            def count(query: str, params: tuple[Any, ...] = ()) -> int:
                return int(conn.execute(query, params).fetchone()[0])

            today = datetime.now(timezone.utc).date().isoformat()
            return {
                "pending_review": count("SELECT COUNT(*) FROM field_verifications WHERE status = 'pending_review'"),
                "approved_today": count("SELECT COUNT(*) FROM field_verifications WHERE status = 'approved' AND date(curator_reviewed_at) = ?", (today,)),
                "needs_more_evidence": count("SELECT COUNT(*) FROM field_verifications WHERE status = 'needs_more_evidence'"),
                "rejected_today": count("SELECT COUNT(*) FROM field_verifications WHERE status = 'rejected' AND date(curator_reviewed_at) = ?", (today,)),
                "training_buffer": count("SELECT COUNT(*) FROM field_verifications WHERE training_eligibility = 'eligible'"),
            }

    def get_training_buffer(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT hazard_type, model_target, COUNT(*) AS count
                FROM field_verifications
                WHERE status = 'approved' AND training_eligibility = 'eligible'
                GROUP BY hazard_type, model_target
                ORDER BY hazard_type
            """).fetchall()
            return [dict(row) for row in rows]

    def get_eligible_reports(self, hazard_type: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM field_verifications
                WHERE hazard_type = ? AND status = 'approved'
                  AND training_eligibility = 'eligible'
                  AND latitude IS NOT NULL AND longitude IS NOT NULL
                  AND observed_at IS NOT NULL
                ORDER BY reported_at
            """, (hazard_type,)).fetchall()
            return [self._decode_row(row) for row in rows]

    def mark_reports_used(self, report_ids: list[int], dataset_version: str) -> None:
        with self.connect() as conn:
            conn.executemany("""
                UPDATE field_verifications
                SET training_eligibility = 'used_in_dataset', dataset_version = ?
                WHERE id = ?
            """, [(dataset_version, report_id) for report_id in report_ids])
            conn.commit()

    def create_dataset(self, manifest: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO training_datasets
                (dataset_version, hazard_type, created_at, record_count, source_reports,
                 source_datasets, feature_schema_version, label_policy_version,
                 curator_version, manifest_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                manifest["dataset_version"], manifest["hazard_type"],
                manifest["created_at"], manifest["record_count"],
                json.dumps(manifest["source_reports"]),
                json.dumps(manifest["source_datasets"]),
                manifest["feature_schema_version"], manifest["label_policy_version"],
                manifest["curator_version"], json.dumps(manifest, ensure_ascii=False),
            ))
            conn.commit()

    def get_latest_dataset_version(self, hazard_type: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("""
                SELECT dataset_version FROM training_datasets
                WHERE hazard_type = ? ORDER BY created_at DESC, id DESC LIMIT 1
            """, (hazard_type,)).fetchone()
            return row["dataset_version"] if row else None
