import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main as backend
import feedback_loop

service = backend._verification_service

report = {
    "reporter_id": "field_officer_17",
    "reporter_role": "field_officer",
    "source_type": "field_officer",
    "source_reference": "warning_93",
    "warning_id": 93,
    "hazard_type": "landslide",
    "classification": "confirmed",
    "description": "Cracks and fresh scar above NH-10 near Chungthang.",
    "observed_at": "2026-09-12T14:30:00+00:00",
    "latitude": 27.645,
    "longitude": 88.585,
    "location_accuracy": 25,
    "photo_reference": "field-photo-001",
    "event_presence": "confirmed",
    "infrastructure_impact": ["NH-10"],
}

submitted = service.submit_report(report)
approved = service.review_report(int(submitted["id"]), {
    "decision": "approved",
    "curator_id": "curator_02",
    "curator_role": "curator",
    "event_presence": "confirmed",
    "notes": "Field image, GPS and warning context support the label.",
})

print("report id        :", submitted["id"])
print("status           :", approved["status"])
print("training_eligible:", approved["training_eligibility"])
print("event_presence   :", approved["event_presence"])

pending = feedback_loop.pending_curated_events()
print("pending now      :", pending["pending"])

version = feedback_loop.next_version_label()
print("next version     :", version)

out = feedback_loop.build_curated_dataset(version)
print("built            :", out.get("built"))
print("rows_built       :", out.get("rows_built"))
print("dataset          :", out.get("dataset"))
print("manifest records :", (out.get("manifest") or {}).get("record_count"))
print("output tail      :", (out.get("output_tail") or "").strip()[-400:])
print("reason           :", out.get("reason"))