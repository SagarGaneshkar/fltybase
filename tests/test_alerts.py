"""Alert and tracker behavior tests."""

from src.alert_engine import AlertEngine
from src.detector import detect_objects
from src.simulator import load_scenario
from src.tracker import Tracker


def process_scenario(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    tracker = Tracker()
    engine = AlertEngine()
    all_alerts = []
    frames_and_alerts = {}
    for frame in load_scenario():
        objects = detect_objects(frame)
        current_states = tracker.update(frame, objects)
        alerts = engine.evaluate(frame, objects, current_states)
        all_alerts.extend(alerts)
        frames_and_alerts[frame.frame_id] = alerts
    return tracker, all_alerts, frames_and_alerts


def test_loitering_and_night_person_alerts_use_context(monkeypatch) -> None:
    _, alerts, by_frame = process_scenario(monkeypatch)
    loitering = [alert for alert in alerts if alert.rule == "LOITERING"]
    night_people = [alert for alert in alerts if alert.rule == "NIGHT_PERSON"]

    assert len(loitering) == 1
    assert loitering[0].timestamp.strftime("%H:%M") == "00:01"
    assert any(alert.timestamp.strftime("%H:%M") == "00:01" for alert in night_people)
    assert not any(alert for alert in by_frame["f015"] if alert.rule == "LOITERING")
    assert not any(alert for alert in by_frame["f029"] if alert.rule == "UNKNOWN_VEHICLE_NIGHT")


def test_telemetry_and_repeat_entry_alerts(monkeypatch) -> None:
    _, alerts, _ = process_scenario(monkeypatch)
    rules = [alert.rule for alert in alerts]

    assert rules.count("TELEMETRY_ALTITUDE") == 1
    assert rules.count("TELEMETRY_BATTERY") == 1
    assert rules.count("REPEAT_ENTRY") == 1
    assert rules.count("UNKNOWN_VEHICLE_NIGHT") == 1


def test_tracker_counts_f150_entries_and_tracks_zones(monkeypatch) -> None:
    tracker, _, _ = process_scenario(monkeypatch)
    state = next(
        value for key, value in tracker.states.items() if "ford f150" in key
    )

    assert tracker.object_counts["blue Ford F150 truck"] == 7
    assert state.count == 7
    assert {"main_gate", "driveway", "garage"}.issubset(state.zones_visited)
