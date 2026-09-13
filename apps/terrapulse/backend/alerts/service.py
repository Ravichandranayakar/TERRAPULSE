import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .cell_broadcast import (
    CellBroadcastGateway,
    SimulatedCellBroadcastGateway,
    build_cell_broadcast_payload,
)
from .schemas import BroadcastDispatchRequest, BroadcastTarget


def _is_polygonal_geometry(geometry: Any) -> bool:
    return isinstance(geometry, dict) and geometry.get("type") in {"Polygon", "MultiPolygon"}


def _risk_cell_polygon(location: dict[str, Any]) -> dict[str, Any] | None:
    bounds = (
        location.get("lon_min"),
        location.get("lat_min"),
        location.get("lon_max"),
        location.get("lat_max"),
    )
    if any(value is None for value in bounds):
        return None
    lon_min, lat_min, lon_max, lat_max = bounds
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon_min, lat_min],
            [lon_max, lat_min],
            [lon_max, lat_max],
            [lon_min, lat_max],
            [lon_min, lat_min],
        ]],
    }


def _resolve_target(
    warning: dict[str, Any],
    location: dict[str, Any] | None,
) -> BroadcastTarget:
    warning_id = int(warning["id"])
    affected = list(warning.get("affected_infrastructure") or [])
    location = location or {}

    warning_geometry = warning.get("geometry")
    if _is_polygonal_geometry(warning_geometry):
        return BroadcastTarget(
            warning_id=warning_id,
            geometry=warning_geometry,
            district=location.get("district"),
            state=location.get("state"),
            region=warning.get("region"),
            affected_infrastructure=affected,
            source="warning_geometry",
        )

    event_geometry = warning.get("event_geometry")
    if _is_polygonal_geometry(event_geometry):
        return BroadcastTarget(
            warning_id=warning_id,
            geometry=event_geometry,
            district=location.get("district"),
            state=location.get("state"),
            region=warning.get("region"),
            affected_infrastructure=affected,
            source="event_geometry",
        )

    risk_cell_geometry = _risk_cell_polygon(location)
    if risk_cell_geometry:
        return BroadcastTarget(
            warning_id=warning_id,
            geometry=risk_cell_geometry,
            district=location.get("district"),
            state=location.get("state"),
            region="nepal_case" if str(location.get("location_id", "")).startswith("NPL_") else "ner_india",
            affected_infrastructure=affected,
            source="risk_cells",
        )

    return BroadcastTarget(
        warning_id=warning_id,
        geometry=None,
        district=location.get("district"),
        state=location.get("state"),
        region=warning.get("region"),
        affected_infrastructure=affected,
        source="demo",
    )


class CellBroadcastService:
    def __init__(self, gateway: CellBroadcastGateway | None = None) -> None:
        self._gateway = gateway or SimulatedCellBroadcastGateway()

    def prepare(
        self,
        warning: dict[str, Any],
        location: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        target = _resolve_target(warning, location)
        prepared_at = datetime.now(timezone.utc)
        expires_at = prepared_at + timedelta(hours=4)
        payload = build_cell_broadcast_payload(
            warning=warning,
            target=target,
            identifier="SIM-CBS-PENDING",
            sent_at=prepared_at,
            expires_at=expires_at,
        )
        return {
            "simulation": True,
            "status": "PREPARED",
            "warning_id": int(warning["id"]),
            "target": target.to_dict(),
            "protocol": {
                "service": "Cell Broadcast Service",
                "standard": "3GPP TS 23.041",
            },
            "payload": payload,
            "prepared_at": prepared_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "audit": {
                "mode": "DEMO",
                "live_network_connected": False,
            },
        }

    def simulate(
        self,
        warning: dict[str, Any],
        location: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        target = _resolve_target(warning, location)
        dispatched_at = datetime.now(timezone.utc)
        expires_at = dispatched_at + timedelta(hours=4)
        broadcast_id = f"SIM-CBS-{dispatched_at:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        payload = build_cell_broadcast_payload(
            warning=warning,
            target=target,
            identifier=broadcast_id,
            sent_at=dispatched_at,
            expires_at=expires_at,
        )
        dispatch_result = self._gateway.dispatch(
            BroadcastDispatchRequest(payload=payload, target=target)
        )

        return {
            "simulation": True,
            "status": dispatch_result.status,
            "broadcast_id": broadcast_id,
            "warning_id": int(warning["id"]),
            "target": target.to_dict(),
            "protocol": {
                "service": "Cell Broadcast Service",
                "standard": "3GPP TS 23.041",
            },
            "payload": payload,
            "network_simulation": dispatch_result.network_simulation,
            "escalation": dispatch_result.escalation,
            "simulation_logs": [
                "[00:00] Loading warning record... ✓",
                "[00:01] Validating target geometry... ✓",
                "[00:02] Generating CAP-compatible alert payload... ✓",
                "[00:03] Preparing Cell Broadcast message... ✓",
                "[00:04] Resolving target geographic cells...",
                "[00:05] Network integration mode: SIMULATION",
                "[00:06] Telecom gateway connection: NOT CONNECTED",
                "[00:07] Simulating cell targeting...",
                "[00:08] Simulating multilingual broadcast payload...",
                "[00:09] Simulating escalation workflow...",
                "[00:10] Dispatch simulation completed ✓",
            ],
            "dispatched_at": dispatched_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "audit": {
                "mode": "DEMO",
                "live_network_connected": False,
                "target_geometry_source": target.source,
            },
        }
