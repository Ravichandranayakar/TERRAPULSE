from dataclasses import dataclass, field
from typing import Any, Literal


BroadcastSource = Literal[
    "warning_geometry",
    "risk_cells",
    "event_geometry",
    "selected_cell",
    "demo",
]


@dataclass(frozen=True)
class BroadcastTarget:
    warning_id: int
    geometry: dict[str, Any] | None
    district: str | None = None
    state: str | None = None
    region: str | None = None
    affected_infrastructure: list[str] = field(default_factory=list)
    source: BroadcastSource = "demo"

    def to_dict(self) -> dict[str, Any]:
        return {
            "warning_id": self.warning_id,
            "geometry": self.geometry,
            "district": self.district,
            "state": self.state,
            "region": self.region,
            "affected_infrastructure": self.affected_infrastructure,
            "source": self.source,
        }


@dataclass(frozen=True)
class BroadcastDispatchRequest:
    payload: dict[str, Any]
    target: BroadcastTarget


@dataclass(frozen=True)
class BroadcastDispatchResult:
    status: str
    network_simulation: dict[str, Any]
    escalation: list[dict[str, str]]
