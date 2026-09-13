import json
from datetime import datetime, timezone
from typing import Any

from .repository import VerificationRepository
from .schemas import (
    EVIDENCE_QUALITY,
    EVENT_PRESENCE,
    HAZARD_TYPES,
    LOCATION_QUALITY,
    MODEL_TARGETS,
    REJECTION_REASONS,
    REPORT_STATUSES,
    SOURCE_TYPES,
    TEMPORAL_QUALITY,
    TRAINING_ELIGIBILITY,
    normalize_event_presence,
    normalize_hazard_type,
)


CURATOR_ROLES = {"curator", "admin", "model_admin"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_timestamp(value: Any) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _location_quality(report: dict[str, Any]) -> str:
    latitude = report.get("latitude")
    longitude = report.get("longitude")
    accuracy = report.get("location_accuracy")
    if latitude is None or longitude is None:
        return "invalid"
    if accuracy is not None and float(accuracy) <= 50:
        return "precise"
    if accuracy is not None and float(accuracy) <= 500:
        return "approximate"
    if report.get("location_quality") in LOCATION_QUALITY:
        return str(report["location_quality"])
    return "approximate" if report.get("source_type") != "demo" else "uncertain"


def _temporal_quality(report: dict[str, Any]) -> str:
    if report.get("temporal_quality") in TEMPORAL_QUALITY:
        return str(report["temporal_quality"])
    return "exact" if _valid_timestamp(report.get("observed_at")) else "unknown"


def _evidence_quality(report: dict[str, Any], location_quality: str, temporal_quality: str) -> str:
    has_description = bool(str(report.get("description") or "").strip())
    has_photo = bool(report.get("photo_reference"))
    if location_quality == "invalid" or temporal_quality == "unknown" or not has_description:
        return "insufficient"
    if has_photo and location_quality == "precise" and temporal_quality == "exact":
        return "high"
    if has_photo or location_quality == "precise":
        return "medium"
    return "low"


class VerificationService:
    def __init__(self, repository: VerificationRepository) -> None:
        self.repository = repository

    def submit_report(self, submitted: dict[str, Any]) -> dict[str, Any]:
        hazard_type = normalize_hazard_type(submitted.get("hazard_type"))
        if hazard_type not in HAZARD_TYPES:
            raise ValueError("Unsupported hazard type.")

        source_type = str(submitted.get("source_type") or "field_officer")
        if source_type not in SOURCE_TYPES:
            raise ValueError("Unsupported source type.")

        location = self.repository.get_location(submitted["location_id"]) if submitted.get("location_id") else None
        latitude = submitted.get("latitude", location.get("centroid_lat") if location else None)
        longitude = submitted.get("longitude", location.get("centroid_lon") if location else None)
        report = {
            **submitted,
            "submitted_hazard_type": normalize_hazard_type(submitted.get("hazard_type")),
            "hazard_type": hazard_type,
            "source_type": source_type,
            "reporter_role": submitted.get("reporter_role") or source_type,
            "submitted_event_presence": normalize_event_presence(submitted.get("event_presence")),
            "event_presence": normalize_event_presence(submitted.get("event_presence")),
            "latitude": float(latitude) if latitude is not None else None,
            "longitude": float(longitude) if longitude is not None else None,
            "geometry": submitted.get("geometry") or (
                {"type": "Point", "coordinates": [float(longitude), float(latitude)]}
                if latitude is not None and longitude is not None else None
            ),
            "infrastructure_impact": submitted.get("infrastructure_impact") or [],
        }
        report["location_quality"] = _location_quality(report)
        report["temporal_quality"] = _temporal_quality(report)
        report["evidence_quality"] = _evidence_quality(
            report, report["location_quality"], report["temporal_quality"]
        )
        report["model_target"] = MODEL_TARGETS[hazard_type]

        report_id = self.repository.insert_report(report)
        duplicates = self.repository.find_candidate_duplicates(
            report_id,
            hazard_type,
            report["latitude"],
            report["longitude"],
            report.get("observed_at"),
        )
        if duplicates:
            self.repository.update_review(
                report_id, {"possible_duplicate_ids": json.dumps(duplicates)}
            )

        result = self.repository.get_report(report_id)
        if result is None:
            raise RuntimeError("Verification report could not be created.")
        result["possible_duplicate_ids"] = duplicates or result.get("possible_duplicate_ids", [])
        result["message"] = "Report submitted for human curator review. It has not modified any deployed model."
        return result

    def get_reports(self, status: str | None = None) -> list[dict[str, Any]]:
        if status and status not in REPORT_STATUSES:
            raise ValueError("Invalid report status.")
        return self.repository.get_reports(status)

    def get_report(self, report_id: int) -> dict[str, Any]:
        report = self.repository.get_report(report_id)
        if report is None:
            raise ValueError(f"Verification report {report_id} was not found.")
        report["audit_events"] = self.repository.get_audit_events(report_id)
        return report

    def review_report(self, report_id: int, decision: dict[str, Any]) -> dict[str, Any]:
        report = self.get_report(report_id)
        action = str(decision.get("decision"))
        if action not in {"approved", "rejected", "needs_more_evidence", "superseded"}:
            raise ValueError("Invalid curator decision.")
        if action != "superseded":
            if not decision.get("curator_id"):
                raise ValueError("Curator ID is required.")
            if decision.get("curator_role") not in CURATOR_ROLES:
                raise ValueError("Curator role is not authorized for this decision.")

        previous_status = report["status"]
        now = _utc_now()
        fields: dict[str, Any] = {
            "status": action,
            "curator_id": decision.get("curator_id"),
            "curator_reviewed_at": now,
            "curator_notes": decision.get("notes"),
        }

        if action == "approved":
            if report["location_quality"] == "invalid":
                raise ValueError("Report cannot enter the training buffer without valid coordinates.")
            if report["temporal_quality"] == "unknown":
                raise ValueError("Report cannot enter the training buffer without event-time information.")
            if report["evidence_quality"] == "insufficient":
                raise ValueError("Report evidence is insufficient for training eligibility.")
            hazard_type = normalize_hazard_type(decision.get("hazard_type") or report["hazard_type"])
            if hazard_type not in HAZARD_TYPES:
                raise ValueError("Unsupported hazard type.")
            event_presence = normalize_event_presence(decision.get("event_presence") or report["event_presence"])
            if event_presence not in EVENT_PRESENCE:
                raise ValueError("Invalid event-presence label.")
            evidence_quality = str(decision.get("evidence_quality") or report["evidence_quality"])
            location_quality = str(decision.get("location_quality") or report["location_quality"])
            if evidence_quality not in EVIDENCE_QUALITY or location_quality not in LOCATION_QUALITY:
                raise ValueError("Invalid quality label.")
            fields.update({
                "hazard_type": hazard_type,
                "event_presence": event_presence,
                "evidence_quality": evidence_quality,
                "location_quality": location_quality,
                "training_eligibility": "eligible",
                "model_target": MODEL_TARGETS[hazard_type],
                "is_approved_for_training": 1,
            })
        elif action == "rejected":
            reason = str(decision.get("reason") or "").lower().replace(" ", "_")
            if reason not in REJECTION_REASONS:
                raise ValueError("A valid rejection reason is required.")
            fields.update({
                "rejection_reason": reason,
                "training_eligibility": "not_eligible",
                "is_approved_for_training": 0,
            })
        elif action == "needs_more_evidence":
            fields.update({
                "training_eligibility": "not_eligible",
                "is_approved_for_training": 0,
            })
        else:
            fields.update({
                "training_eligibility": "not_eligible",
                "is_approved_for_training": 0,
            })

        self.repository.update_review(report_id, fields)
        self.repository.insert_audit_event({
            "report_id": report_id,
            "action": action,
            "curator_id": decision.get("curator_id"),
            "timestamp": now,
            "previous_status": previous_status,
            "new_status": action,
            "notes": decision.get("notes"),
        })
        return self.get_report(report_id)

    def get_stats(self) -> dict[str, int]:
        return self.repository.get_stats()

    def get_training_buffer(self) -> list[dict[str, Any]]:
        return self.repository.get_training_buffer()

    def build_dataset(self, hazard_type: str, curator_id: str) -> dict[str, Any]:
        hazard_type = normalize_hazard_type(hazard_type)
        if hazard_type not in {"landslide", "flood", "debris_flow"}:
            raise ValueError("Dataset builds are currently supported for landslide, flood, and debris_flow models.")
        if not curator_id:
            raise ValueError("Curator ID is required.")

        reports = self.repository.get_eligible_reports(hazard_type)
        report_ids = [int(report["id"]) for report in reports]
        latest_version = self.repository.get_latest_dataset_version(hazard_type)
        if latest_version:
            try:
                minor = int(latest_version.rsplit("v", 1)[1].split(".")[1]) + 1
            except (IndexError, ValueError):
                minor = 1
        else:
            minor = 1
        dataset_version = f"{hazard_type}-v0.{minor}"
        manifest = {
            "dataset_version": dataset_version,
            "hazard_type": hazard_type,
            "created_at": _utc_now(),
            "record_count": len(report_ids),
            "source_reports": report_ids,
            "source_datasets": [],
            "feature_schema_version": "1.0",
            "label_policy_version": "1.0",
            "curator_version": "1.0",
            "training_status": "not_automatically_run",
            "model_updated": False,
        }
        self.repository.create_dataset(manifest)
        if report_ids:
            self.repository.mark_reports_used(report_ids, dataset_version)
        return manifest
