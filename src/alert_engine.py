"""Rule-based security alert generation."""

from __future__ import annotations

from datetime import datetime, time

from src.models import Alert, DetectedObject, Frame
from src.tracker import ObjectState, object_identity


ALERT_RULES = {
    "LOITERING": {"consecutive_frames": 3, "duration_seconds": 120, "severity": "HIGH"},
    "NIGHT_PERSON": {"start": "22:00", "end": "05:00", "severity": "HIGH"},
    "UNKNOWN_VEHICLE_NIGHT": {
        "start": "22:00",
        "end": "05:00",
        "severity": "MEDIUM",
    },
    "REPEAT_ENTRY": {"minimum_entries": 2, "severity": "LOW"},
    "TELEMETRY_ALTITUDE": {"minimum_m": 5, "maximum_m": 120, "severity": "MEDIUM"},
    "TELEMETRY_BATTERY": {"minimum_pct": 20, "severity": "MEDIUM"},
}
KNOWN_VEHICLES = {"ford f150", "delivery van"}


def _is_night(timestamp: datetime) -> bool:
    local_time = timestamp.time()
    return local_time >= time(22, 0) or local_time < time(5, 0)


class AlertEngine:
    """Evaluate configured safety/security rules and suppress duplicate notices."""

    def __init__(self) -> None:
        self._alerted: set[tuple[str, str]] = set()
        self._entry_counts: dict[str, int] = {}
        self._repeat_alerted: set[str] = set()

    def _emit_once(
        self,
        frame: Frame,
        rule: str,
        identity: str,
        message: str,
        severity: str,
        timestamp: datetime | None = None,
    ) -> Alert | None:
        key = (rule, identity)
        if key in self._alerted:
            return None
        self._alerted.add(key)
        return Alert(
            frame_id=frame.frame_id,
            timestamp=timestamp or frame.timestamp,
            rule=rule,
            severity=severity,  # type: ignore[arg-type]
            message=message,
        )

    def evaluate(
        self,
        frame: Frame,
        objects: list[DetectedObject],
        current_states: dict[str, ObjectState],
    ) -> list[Alert]:
        alerts: list[Alert] = []
        is_night = _is_night(frame.timestamp)
        for obj in objects:
            identity = object_identity(obj)
            state = current_states[identity]
            if obj.type == "person":
                if is_night:
                    alert = self._emit_once(
                        frame,
                        "NIGHT_PERSON",
                        identity,
                        f"Person detected at {obj.zone}, {frame.timestamp:%H:%M}",
                        ALERT_RULES["NIGHT_PERSON"]["severity"],
                    )
                    if alert:
                        alerts.append(alert)
                if (
                    state.consecutive_frames >= ALERT_RULES["LOITERING"]["consecutive_frames"]
                    or (
                        frame.timestamp - state.first_seen
                    ).total_seconds() >= ALERT_RULES["LOITERING"]["duration_seconds"]
                ):
                    alert = self._emit_once(
                        frame,
                        "LOITERING",
                        identity,
                        f"Person loitering at {obj.zone}, {state.first_seen:%H:%M}",
                        ALERT_RULES["LOITERING"]["severity"],
                        timestamp=state.first_seen,
                    )
                    if alert:
                        alerts.append(alert)

            if obj.type == "vehicle":
                normalized_model = (obj.make_model or "").lower()
                if is_night and normalized_model not in KNOWN_VEHICLES:
                    alert = self._emit_once(
                        frame,
                        "UNKNOWN_VEHICLE_NIGHT",
                        identity,
                        f"Unknown vehicle at {obj.zone}, {frame.timestamp:%H:%M}",
                        ALERT_RULES["UNKNOWN_VEHICLE_NIGHT"]["severity"],
                    )
                    if alert:
                        alerts.append(alert)
                if obj.activity == "entering":
                    self._entry_counts[identity] = self._entry_counts.get(identity, 0) + 1
                    if (
                        self._entry_counts[identity]
                        >= ALERT_RULES["REPEAT_ENTRY"]["minimum_entries"]
                        and identity not in self._repeat_alerted
                    ):
                        self._repeat_alerted.add(identity)
                        alerts.append(
                            Alert(
                                frame_id=frame.frame_id,
                                timestamp=frame.timestamp,
                                rule="REPEAT_ENTRY",
                                severity=ALERT_RULES["REPEAT_ENTRY"]["severity"],  # type: ignore[arg-type]
                                message=f"Repeat vehicle entry: {obj.label}, {frame.timestamp:%H:%M}",
                            )
                        )

        telemetry = frame.telemetry
        if not (
            ALERT_RULES["TELEMETRY_ALTITUDE"]["minimum_m"]
            <= telemetry.altitude_m
            <= ALERT_RULES["TELEMETRY_ALTITUDE"]["maximum_m"]
        ):
            alerts.append(
                Alert(
                    frame_id=frame.frame_id,
                    timestamp=frame.timestamp,
                    rule="TELEMETRY_ALTITUDE",
                    severity=ALERT_RULES["TELEMETRY_ALTITUDE"]["severity"],  # type: ignore[arg-type]
                    message=f"Altitude anomaly: {telemetry.altitude_m:g} m at {frame.telemetry.zone}, {frame.timestamp:%H:%M}",
                )
            )
        if telemetry.battery_pct < ALERT_RULES["TELEMETRY_BATTERY"]["minimum_pct"]:
            alerts.append(
                Alert(
                    frame_id=frame.frame_id,
                    timestamp=frame.timestamp,
                    rule="TELEMETRY_BATTERY",
                    severity=ALERT_RULES["TELEMETRY_BATTERY"]["severity"],  # type: ignore[arg-type]
                    message=f"Low battery: {telemetry.battery_pct:g}% at {frame.timestamp:%H:%M}",
                )
            )
        return alerts
