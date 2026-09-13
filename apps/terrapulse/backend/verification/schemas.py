from typing import Any, Literal


HazardType = Literal["landslide", "flood", "debris_flow", "other", "unknown"]
ReportStatus = Literal[
    "pending_review",
    "approved",
    "rejected",
    "needs_more_evidence",
    "superseded",
]
TrainingEligibility = Literal["not_eligible", "eligible", "used_in_dataset"]
SourceType = Literal[
    "citizen",
    "field_officer",
    "admin",
    "imported_inventory",
    "satellite_reference",
    "historical_dataset",
    "demo",
]
EvidenceQuality = Literal["high", "medium", "low", "insufficient"]
LocationQuality = Literal["precise", "approximate", "uncertain", "invalid"]
TemporalQuality = Literal["exact", "approximate", "unknown"]
EventPresence = Literal["confirmed", "not_observed", "uncertain"]

HAZARD_TYPES = {"landslide", "flood", "debris_flow", "other", "unknown"}
REPORT_STATUSES = {
    "pending_review",
    "approved",
    "rejected",
    "needs_more_evidence",
    "superseded",
}
TRAINING_ELIGIBILITY = {"not_eligible", "eligible", "used_in_dataset"}
SOURCE_TYPES = {
    "citizen",
    "field_officer",
    "admin",
    "imported_inventory",
    "satellite_reference",
    "historical_dataset",
    "demo",
}
EVIDENCE_QUALITY = {"high", "medium", "low", "insufficient"}
LOCATION_QUALITY = {"precise", "approximate", "uncertain", "invalid"}
TEMPORAL_QUALITY = {"exact", "approximate", "unknown"}
EVENT_PRESENCE = {"confirmed", "not_observed", "uncertain"}
REJECTION_REASONS = {
    "incorrect_hazard",
    "incorrect_location",
    "insufficient_evidence",
    "duplicate",
    "invalid_report",
    "outside_study_area",
    "other",
}
MODEL_TARGETS = {
    "landslide": "landslide_model",
    "flood": "flood_model",
    "debris_flow": "debris_flow_model",
    "other": "multi_hazard_review",
    "unknown": "multi_hazard_review",
}


def normalize_hazard_type(value: Any) -> str:
    hazard = str(value or "unknown").lower().replace("-", "_")
    if hazard in {"road_crack", "slope_movement"}:
        return "landslide"
    if hazard in {"flooding", "flood"}:
        return "flood"
    if hazard == "debris":
        return "debris_flow"
    return hazard if hazard in HAZARD_TYPES else "unknown"


def normalize_event_presence(value: Any) -> str:
    normalized = str(value or "uncertain").lower().replace(" ", "_")
    if normalized in {"confirmed", "yes", "true"}:
        return "confirmed"
    if normalized in {"false_alarm", "not_observed", "no", "false"}:
        return "not_observed"
    return "uncertain"
