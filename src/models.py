"""Typed data models for the drone security pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ObjectType = Literal["person", "vehicle", "animal", "other"]
Severity = Literal["HIGH", "MEDIUM", "LOW"]


@dataclass(frozen=True)
class Telemetry:
    zone: str
    lat: float
    lon: float
    altitude_m: float
    battery_pct: float
    speed_mps: float


@dataclass(frozen=True)
class Frame:
    frame_id: str
    timestamp: datetime
    telemetry: Telemetry
    description: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Frame:
        telemetry_data = data["telemetry"]
        if not isinstance(telemetry_data, dict):
            raise ValueError("Frame telemetry must be an object")
        timestamp = datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00"))
        telemetry = Telemetry(
            zone=str(telemetry_data["zone"]),
            lat=float(telemetry_data["lat"]),
            lon=float(telemetry_data["lon"]),
            altitude_m=float(telemetry_data["altitude_m"]),
            battery_pct=float(telemetry_data["battery_pct"]),
            speed_mps=float(telemetry_data["speed_mps"]),
        )
        return cls(
            frame_id=str(data["frame_id"]),
            timestamp=timestamp,
            telemetry=telemetry,
            description=str(data["description"]),
        )


@dataclass(frozen=True)
class DetectedObject:
    type: ObjectType
    color: str | None
    make_model: str | None
    activity: str
    zone: str
    label: str


@dataclass(frozen=True)
class Alert:
    frame_id: str
    timestamp: datetime
    rule: str
    severity: Severity
    message: str
