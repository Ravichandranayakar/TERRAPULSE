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

class TwilioCellBroadcastGateway:
    """Sends real SMS messages to demo target phone numbers using Twilio."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        try:
            from twilio.rest import Client
            self.client = Client(account_sid, auth_token)
            self.from_number = from_number
        except ImportError:
            self.client = None

    def dispatch(self, payload: BroadcastDispatchRequest) -> BroadcastDispatchResult:
        if not self.client:
            return BroadcastDispatchResult(
                status="FAILED",
                network_simulation={"status": "TWILIO_NOT_INSTALLED", "target_cells": [], "estimated_devices": 0},
                escalation=[],
            )

        messages = payload.payload.get("messages", [])
        sms_body = "TerraPulse Early Warning"
        for m in messages:
            if m.get("language") == "en":
                sms_body = f"[{m.get('headline')}] {m.get('description')} {m.get('instruction')}"
                break
        
        success_count = 0
        phone_numbers = payload.demo_phone_numbers

        if not phone_numbers:
             return BroadcastDispatchResult(
                status="NO_TARGETS_PROVIDED",
                network_simulation={"status": "SKIPPED", "target_cells": [], "estimated_devices": 0},
                escalation=[],
            )

        for number in phone_numbers:
            try:
                self.client.messages.create(
                    body=sms_body,
                    from_=self.from_number,
                    to=number
                )
                success_count += 1
            except Exception as e:
                pass # Logging can be added later

        return BroadcastDispatchResult(
            status="DELIVERED_VIA_TWILIO",
            network_simulation={
                "status": "LIVE_DEMO",
                "target_cells": [],
                "estimated_devices": success_count,
            },
            escalation=[
                {"entity": f"Sent SMS to {success_count} team members", "status": "DELIVERED"},
                {"entity": "District administration", "status": "SIMULATED"},
                {"entity": "Road authority / control room", "status": "SIMULATED"},
                {"entity": "Police / emergency response", "status": "SIMULATED"},
                {"entity": "State disaster management authority", "status": "SIMULATED"},
            ],
        )

class NtfyCellBroadcastGateway:
    """Sends real push notifications to ntfy.sh topics."""
    
    def dispatch(self, payload: BroadcastDispatchRequest) -> BroadcastDispatchResult:
        import urllib.request
        
        messages = payload.payload.get("messages", [])
        alert_body = "TerraPulse Early Warning"
        alert_title = "Landslide Warning"
        for m in messages:
            if m.get("language") == "en":
                alert_title = m.get("headline", alert_title)
                alert_body = f"{m.get('description')} {m.get('instruction')}"
                break
        
        success_count = 0
        topics = payload.demo_phone_numbers

        if not topics:
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

        for topic in topics:
            try:
                # topic could be a phone number or a string. ntfy topics just need to be valid URLs.
                # strip out spaces or special characters just in case
                clean_topic = "".join(c for c in str(topic) if c.isalnum() or c in "-_")
                if not clean_topic:
                    continue
                    
                req = urllib.request.Request(
                    f"https://ntfy.sh/{clean_topic}",
                    data=alert_body.encode("utf-8"),
                    headers={
                        "Title": alert_title,
                        "Priority": "urgent",
                        "Tags": "warning,rotating_light"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        success_count += 1
            except Exception as e:
                import traceback
                traceback.print_exc()
                pass # Fail silently for the demo
        return BroadcastDispatchResult(
            status="DELIVERED_VIA_NTFY",
            network_simulation={
                "status": "LIVE_DEMO",
                "target_cells": [],
                "estimated_devices": success_count,
            },
            escalation=[
                {"entity": f"Sent push notification to {success_count} ntfy topics", "status": "DELIVERED"},
                {"entity": "District administration", "status": "SIMULATED"},
                {"entity": "Road authority / control room", "status": "SIMULATED"},
                {"entity": "Police / emergency response", "status": "SIMULATED"},
                {"entity": "State disaster management authority", "status": "SIMULATED"},
            ],
        )
