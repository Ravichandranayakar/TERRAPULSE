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
    """Sends real push notifications to public ntfy.sh topics.

    A topic is the subscription key typed into the ntfy app. ntfy only shows a
    message on devices subscribed to the exact same topic name, so an unusable
    topic is reported back instead of being silently rewritten.
    """

    TOPIC_ALPHABET = frozenset(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    )
    MAX_TOPIC_LENGTH = 64

    def _validate_topic(self, raw_topic: Any) -> tuple[str | None, str | None]:
        topic = str(raw_topic or "").strip()
        if not topic:
            return None, "No topic name was given."
        if len(topic) > self.MAX_TOPIC_LENGTH:
            return None, (
                "Topic name is "
                + str(len(topic))
                + " characters long; ntfy allows at most "
                + str(self.MAX_TOPIC_LENGTH)
                + "."
            )
        invalid = sorted(
            {character for character in topic if character not in self.TOPIC_ALPHABET}
        )
        if invalid:
            return None, (
                "Topic name contains characters ntfy does not allow: "
                + " ".join(repr(character) for character in invalid)
                + ". Use only letters, numbers, hyphen (-) and underscore (_)."
            )
        return topic, None

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

        topics = [str(topic) for topic in payload.demo_phone_numbers]

        if not topics:
            print(
                "[TERRAPULSE] Cell broadcast: no ntfy topic given, simulation only "
                "(no push notification sent)"
            )
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

        deliveries: list[dict[str, str]] = []
        success_count = 0

        for raw_topic in topics:
            topic, problem = self._validate_topic(raw_topic)
            if problem:
                deliveries.append(
                    {
                        "topic": str(raw_topic).strip(),
                        "status": "REJECTED",
                        "detail": problem,
                    }
                )
                continue

            try:
                request = urllib.request.Request(
                    f"https://ntfy.sh/{topic}",
                    data=alert_body.encode("utf-8"),
                    headers={
                        "Title": alert_title,
                        "Priority": "urgent",
                        "Tags": "warning,rotating_light",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    http_status = response.status
            except Exception as exc:
                deliveries.append(
                    {
                        "topic": topic,
                        "status": "FAILED",
                        "detail": type(exc).__name__ + ": " + str(exc),
                    }
                )
                continue

            if http_status == 200:
                success_count += 1
                deliveries.append(
                    {
                        "topic": topic,
                        "status": "SENT",
                        "detail": "ntfy.sh accepted the message for this topic.",
                    }
                )
            else:
                deliveries.append(
                    {
                        "topic": topic,
                        "status": "FAILED",
                        "detail": "ntfy.sh returned HTTP " + str(http_status) + ".",
                    }
                )

        if success_count == 0:
            status = "DELIVERY_FAILED"
        elif success_count < len(topics):
            status = "PARTIALLY_DELIVERED_VIA_NTFY"
        else:
            status = "DELIVERED_VIA_NTFY"

        summary = ", ".join(
            item["topic"] + "=" + item["status"] for item in deliveries
        )
        print(
            "[TERRAPULSE] Cell broadcast "
            + status
            + " ("
            + str(success_count)
            + "/"
            + str(len(topics))
            + " delivered)"
            + (": " + summary if summary else "")
        )
        for item in deliveries:
            if item["status"] != "SENT":
                print("[TERRAPULSE]   " + item["topic"] + ": " + item["detail"])

        sent_topics = [
            item["topic"] for item in deliveries if item["status"] == "SENT"
        ]
        if sent_topics:
            entity = "Published to ntfy.sh topic(s): " + ", ".join(sent_topics)
            entity_status = "DELIVERED"
        else:
            entity = "ntfy.sh push delivery failed for every topic"
            entity_status = "FAILED"

        return BroadcastDispatchResult(
            status=status,
            network_simulation={
                "status": "LIVE_DEMO" if success_count else "LIVE_DEMO_FAILED",
                "target_cells": [],
                "estimated_devices": success_count,
                "deliveries": deliveries,
                "note": (
                    "ntfy.sh accepted the message. A device shows it only when the ntfy app "
                    "is subscribed to the exact same topic name (topics are case-sensitive)."
                ),
            },
            escalation=[
                {"entity": entity, "status": entity_status},
                {"entity": "District administration", "status": "SIMULATED"},
                {"entity": "Road authority / control room", "status": "SIMULATED"},
                {"entity": "Police / emergency response", "status": "SIMULATED"},
                {"entity": "State disaster management authority", "status": "SIMULATED"},
            ],
        )
