from datetime import datetime
from typing import Any, Protocol

from .schemas import BroadcastDispatchRequest, BroadcastDispatchResult, BroadcastTarget


BROADCAST_LANGUAGES = ("en", "hi", "ne")


def warning_to_alert_parameters(warning: dict[str, Any]) -> dict[str, str]:
    """Map existing TerraPulse warning semantics to CAP-compatible values."""
    risk_level = str(warning.get("risk_level", "low")).lower()
    if risk_level == "critical":
        return {"severity": "Extreme", "urgency": "Immediate", "certainty": "Likely"}
    if risk_level == "high":
        return {"severity": "Severe", "urgency": "Expected", "certainty": "Likely"}
    if risk_level == "moderate":
        return {"severity": "Moderate", "urgency": "Future", "certainty": "Possible"}
    return {"severity": "Minor", "urgency": "Future", "certainty": "Unlikely"}


def _infrastructure_text(affected_infrastructure: list[str]) -> str:
    if not affected_infrastructure:
        return "Nearby infrastructure may be affected."
    return f"{', '.join(affected_infrastructure)} may be affected."


def _message(
    language: str,
    location_name: str,
    affected_infrastructure: list[str],
) -> dict[str, str]:
    infrastructure = _infrastructure_text(affected_infrastructure)
    if language == "hi":
        return {
            "language": "hi",
            "headline": "भूस्खलन चेतावनी",
            "description": f"{location_name} के पास उच्च भूस्खलन जोखिम की पहचान हुई है। {infrastructure}",
            "instruction": "प्रभावित क्षेत्र से बचें और स्थानीय प्रशासन के निर्देशों का पालन करें।",
        }
    if language == "ne":
        return {
            "language": "ne",
            "headline": "पहिरो चेतावनी",
            "description": f"{location_name} नजिक उच्च पहिरो जोखिम पहिचान भएको छ। {infrastructure}",
            "instruction": "प्रभावित क्षेत्रबाट बच्नुहोस् र स्थानीय अधिकारीको निर्देश पालना गर्नुहोस्।",
        }
    return {
        "language": "en",
        "headline": "Landslide Warning",
        "description": f"High landslide risk detected near {location_name}. {infrastructure}",
        "instruction": "Avoid the affected area and follow instructions from local authorities.",
    }


def build_cell_broadcast_payload(
    warning: dict[str, Any],
    target: BroadcastTarget,
    identifier: str,
    sent_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    parameters = warning_to_alert_parameters(warning)
    location_name = str(warning.get("location_name") or "the affected area")
    area_name = ", ".join(
        part for part in (target.district, target.state) if part
    ) or location_name
    messages = [
        _message(language, location_name, target.affected_infrastructure)
        for language in BROADCAST_LANGUAGES
    ]

    return {
        "format": "CAP-compatible",
        "identifier": identifier,
        "sender": "TerraPulse Emergency Warning System",
        "sent": sent_at.isoformat(),
        "status": "Exercise",
        "msgType": "Alert",
        "scope": "Public",
        "languages": list(BROADCAST_LANGUAGES),
        "severity": parameters["severity"],
        "urgency": parameters["urgency"],
        "certainty": parameters["certainty"],
        "effective": sent_at.isoformat(),
        "expires": expires_at.isoformat(),
        "area": area_name,
        "polygon": target.geometry,
        "circle": None,
        "messages": messages,
        "info": [
            {
                "language": message["language"],
                "event": "Landslide Risk Warning",
                "urgency": parameters["urgency"],
                "severity": parameters["severity"],
                "certainty": parameters["certainty"],
                "effective": sent_at.isoformat(),
                "expires": expires_at.isoformat(),
                "area": area_name,
                "polygon": target.geometry,
                "circle": None,
                "headline": message["headline"],
                "description": message["description"],
                "instruction": message["instruction"],
            }
            for message in messages
        ],
    }


class CellBroadcastGateway(Protocol):
    def dispatch(self, payload: BroadcastDispatchRequest) -> BroadcastDispatchResult:
        """Submit a cell-broadcast request at the integration boundary."""


class SimulatedCellBroadcastGateway:
    """Honest simulation boundary; no telecom or government system is contacted."""

    def dispatch(self, payload: BroadcastDispatchRequest) -> BroadcastDispatchResult:
        return BroadcastDispatchResult(
            status="SIMULATED_DISPATCH",
            network_simulation={
                "status": "SIMULATED",
                "target_cells": [],
                "estimated_devices": None,
            },
            escalation=[
                {"entity": "District administration", "status": "SIMULATED"},
                {"entity": "Road authority / control room", "status": "SIMULATED"},
                {"entity": "Police / emergency response", "status": "SIMULATED"},
                {"entity": "State disaster management authority", "status": "SIMULATED"},
            ],
        )
