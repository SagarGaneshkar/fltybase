"""Cross-frame object context and daily summary tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.models import DetectedObject, Frame


@dataclass
class ObjectState:
    identity: str
    first_seen: datetime
    last_seen: datetime
    count: int = 0
    consecutive_frames: int = 0
    zones_visited: list[str] = field(default_factory=list)
    last_zone: str = ""
    last_frame_index: int = -1


def object_identity(obj: DetectedObject) -> str:
    if obj.type == "vehicle":
        identity = " ".join(
            part for part in (obj.color, obj.make_model) if part
        ).lower()
        return f"vehicle:{identity or obj.label.lower()}"
    if obj.type == "person":
        return f"person:{obj.zone}:{obj.color or 'unknown'}"
    return f"{obj.type}:{obj.make_model or obj.label}".lower()


class Tracker:
    """Retain object state across frames and provide a day-level recap."""

    def __init__(self) -> None:
        self.states: dict[str, ObjectState] = {}
        self.object_counts: dict[str, int] = {}
        self.frame_count = 0

    def update(
        self, frame: Frame, objects: list[DetectedObject]
    ) -> dict[str, ObjectState]:
        self.frame_count += 1
        current: dict[str, ObjectState] = {}
        for obj in objects:
            identity = object_identity(obj)
            state = self.states.get(identity)
            if state is None:
                state = ObjectState(
                    identity=identity,
                    first_seen=frame.timestamp,
                    last_seen=frame.timestamp,
                )
                self.states[identity] = state

            if state.last_frame_index == self.frame_count - 1 and state.last_zone == obj.zone:
                state.consecutive_frames += 1
            else:
                state.consecutive_frames = 1
            state.last_seen = frame.timestamp
            state.count += 1
            state.last_zone = obj.zone
            state.last_frame_index = self.frame_count
            if obj.zone not in state.zones_visited:
                state.zones_visited.append(obj.zone)
            current[identity] = state
            self.object_counts[obj.label] = self.object_counts.get(obj.label, 0) + 1
        return current

    def summary(self) -> dict[str, object]:
        return {
            "frames_processed": self.frame_count,
            "object_events": sum(self.object_counts.values()),
            "objects_by_label": dict(sorted(self.object_counts.items())),
            "zones_visited": sorted(
                {zone for state in self.states.values() for zone in state.zones_visited}
            ),
        }
