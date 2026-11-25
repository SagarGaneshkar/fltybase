"""Detector behavior tests."""

from datetime import datetime

from src.detector import detect_objects
from src.models import Frame, Telemetry


def make_frame(description: str, zone: str = "main_gate") -> Frame:
    return Frame(
        frame_id="test",
        timestamp=datetime(2025, 1, 15, 7, 10),
        telemetry=Telemetry(zone, 0.0, 0.0, 35.0, 90.0, 2.0),
        description=description,
    )


def test_extracts_truck_color_make_and_activity(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = detect_objects(make_frame("A blue Ford F150 is entering the main gate."))

    assert len(result) == 1
    assert result[0].type == "vehicle"
    assert result[0].color == "blue"
    assert result[0].make_model == "Ford F150"
    assert result[0].activity == "entering"
    assert result[0].zone == "main_gate"


def test_empty_and_malformed_descriptions_return_no_objects(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert detect_objects(make_frame("")) == []
    assert detect_objects(make_frame("??? [unreadable feed]")) == []
    assert detect_objects(make_frame("No vehicle or pedestrian at the entrance.")) == []


def test_extracts_person_and_vehicle_from_same_description(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = detect_objects(make_frame("A person stands beside a red sedan."))

    assert {item.type for item in result} == {"person", "vehicle"}
