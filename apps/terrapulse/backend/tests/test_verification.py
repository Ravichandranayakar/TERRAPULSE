import tempfile
import sqlite3
import unittest
from pathlib import Path

from verification.repository import VerificationRepository
from verification.service import VerificationService


class VerificationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = str(Path(self.temp_dir.name) / "verification.db")
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("""
                CREATE TABLE monitoring_locations (
                    location_id TEXT PRIMARY KEY,
                    centroid_lat REAL,
                    centroid_lon REAL
                )
            """)
            connection.execute("""
                CREATE TABLE landslide_warnings (
                    id INTEGER PRIMARY KEY,
                    location_name TEXT,
                    risk_level TEXT,
                    risk_score REAL
                )
            """)
            connection.commit()
        finally:
            connection.close()
        self.repository = VerificationRepository(self.db_path)
        self.repository.ensure_schema()
        self.service = VerificationService(self.repository)

    def submit_report(self, **overrides):
        report = {
            "reporter_id": "field_officer_17",
            "reporter_role": "field_officer",
            "source_type": "field_officer",
            "source_reference": "warning_93",
            "warning_id": 93,
            "hazard_type": "landslide",
            "classification": "confirmed",
            "description": "Large cracks observed along the slope above NH-10.",
            "observed_at": "2026-09-12T14:30:00+00:00",
            "latitude": 27.645,
            "longitude": 88.585,
            "location_accuracy": 25,
            "photo_reference": "field-photo-001",
            "event_presence": "confirmed",
            "infrastructure_impact": ["NH-10"],
        }
        report.update(overrides)
        return self.service.submit_report(report)

    def review(self, report_id, **overrides):
        decision = {
            "decision": "approved",
            "curator_id": "curator_02",
            "curator_role": "curator",
            "event_presence": "confirmed",
            "notes": "Field image, GPS, and warning context support the label.",
        }
        decision.update(overrides)
        return self.service.review_report(report_id, decision)

    def test_citizen_and_field_reports_start_pending(self):
        citizen = self.submit_report(
            reporter_id="citizen_01",
            reporter_role="citizen",
            source_type="citizen",
            source_reference="citizen_portal",
        )
        field = self.submit_report()

        self.assertEqual("pending_review", citizen["status"])
        self.assertEqual("pending_review", field["status"])
        self.assertEqual("not_eligible", citizen["training_eligibility"])
        self.assertEqual("not_eligible", field["training_eligibility"])

    def test_approval_creates_eligible_training_record_without_model_update(self):
        report = self.submit_report()
        approved = self.review(int(report["id"]))

        self.assertEqual("approved", approved["status"])
        self.assertEqual("eligible", approved["training_eligibility"])
        self.assertEqual("landslide_model", approved["model_target"])
        self.assertEqual(1, approved["is_approved_for_training"])
        self.assertEqual("precise", approved["location_quality"])
        self.assertEqual("exact", approved["temporal_quality"])
        self.assertEqual("high", approved["evidence_quality"])

    def test_rejection_requires_reason_and_excludes_report(self):
        report = self.submit_report()
        rejected = self.review(
            int(report["id"]),
            decision="rejected",
            reason="duplicate",
            notes="Same event already represented by an earlier report.",
        )

        self.assertEqual("rejected", rejected["status"])
        self.assertEqual("not_eligible", rejected["training_eligibility"])
        self.assertEqual("duplicate", rejected["rejection_reason"])
        self.assertEqual(0, rejected["is_approved_for_training"])

    def test_needs_more_evidence_excludes_report(self):
        report = self.submit_report()
        result = self.review(
            int(report["id"]),
            decision="needs_more_evidence",
            notes="Request a closer photograph and confirmation of event time.",
        )

        self.assertEqual("needs_more_evidence", result["status"])
        self.assertEqual("not_eligible", result["training_eligibility"])
        self.assertEqual([], self.service.get_training_buffer())

    def test_nearby_similar_reports_are_flagged_for_curator_review(self):
        first = self.submit_report()
        second = self.submit_report(description="Second report for the same slope failure.")

        self.assertEqual([], first["possible_duplicate_ids"])
        self.assertEqual([int(first["id"])], second["possible_duplicate_ids"])

    def test_hazard_routing_and_real_training_buffer_counts(self):
        landslide = self.submit_report()
        flood = self.submit_report(hazard_type="flood", latitude=27.2, longitude=88.1)
        debris_flow = self.submit_report(hazard_type="debris_flow", latitude=27.8, longitude=88.9)

        self.review(int(landslide["id"]))
        self.review(int(flood["id"]))
        self.review(int(debris_flow["id"]))

        buffer = self.service.get_training_buffer()
        self.assertEqual(
            [
                {"hazard_type": "debris_flow", "model_target": "debris_flow_model", "count": 1},
                {"hazard_type": "flood", "model_target": "flood_model", "count": 1},
                {"hazard_type": "landslide", "model_target": "landslide_model", "count": 1},
            ],
            buffer,
        )

    def test_curator_actions_create_audit_records(self):
        report = self.submit_report()
        approved = self.review(int(report["id"]))

        audit_events = approved["audit_events"]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("pending_review", audit_events[0]["previous_status"])
        self.assertEqual("approved", audit_events[0]["new_status"])
        self.assertEqual("curator_02", audit_events[0]["curator_id"])

    def test_curator_correction_preserves_raw_submitted_labels(self):
        report = self.submit_report(hazard_type="flood")
        approved = self.review(int(report["id"]), hazard_type="landslide")

        self.assertEqual("flood", approved["submitted_hazard_type"])
        self.assertEqual("landslide", approved["hazard_type"])
        self.assertEqual("confirmed", approved["submitted_event_presence"])

    def test_dataset_builder_includes_only_approved_eligible_records(self):
        approved = self.submit_report()
        pending = self.submit_report(
            description="Pending report should not be included.",
            latitude=27.65,
        )
        rejected = self.submit_report(
            description="Rejected report should not be included.",
            latitude=27.66,
        )

        self.review(int(approved["id"]))
        self.review(
            int(rejected["id"]),
            decision="rejected",
            reason="insufficient_evidence",
        )

        manifest = self.service.build_dataset("landslide", "model_admin_01")
        self.assertEqual([int(approved["id"])], manifest["source_reports"])
        self.assertEqual(1, manifest["record_count"])
        self.assertEqual("not_automatically_run", manifest["training_status"])
        self.assertFalse(manifest["model_updated"])
        self.assertNotIn(int(pending["id"]), manifest["source_reports"])
        self.assertNotIn(int(rejected["id"]), manifest["source_reports"])

        used = self.service.get_report(int(approved["id"]))
        self.assertEqual("used_in_dataset", used["training_eligibility"])
        self.assertEqual(manifest["dataset_version"], used["dataset_version"])

    def test_insufficient_report_cannot_be_approved(self):
        report = self.submit_report(
            description="",
            photo_reference=None,
            observed_at=None,
            latitude=None,
            longitude=None,
        )

        with self.assertRaisesRegex(ValueError, "valid coordinates"):
            self.review(int(report["id"]))


if __name__ == "__main__":
    unittest.main()
