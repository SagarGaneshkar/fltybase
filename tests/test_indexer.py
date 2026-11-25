"""SQLite indexer behavior tests."""

from src.alert_engine import AlertEngine
from src.detector import detect_objects
from src.indexer import Indexer
from src.simulator import load_scenario
from src.tracker import Tracker


def build_index(monkeypatch) -> Indexer:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    indexer = Indexer()
    tracker = Tracker()
    alert_engine = AlertEngine()
    for frame in load_scenario():
        objects = detect_objects(frame)
        states = tracker.update(frame, objects)
        alerts = alert_engine.evaluate(frame, objects, states)
        indexer.add_frame(frame, objects, alerts)
    return indexer


def test_query_by_time_and_object_returns_expected_frame_context(monkeypatch) -> None:
    indexer = build_index(monkeypatch)
    morning = indexer.query_by_time("07:00", "07:30")
    trucks = indexer.query_by_object(type="truck")

    assert [frame["id"] for frame in morning] == ["f016", "f017"]
    assert len(trucks) == 7
    assert any(obj["make_model"] == "Ford F150" for obj in trucks[0]["objects"])


def test_search_text_and_event_counts(monkeypatch) -> None:
    indexer = build_index(monkeypatch)

    results = indexer.search_text("perimeter fence")
    assert results
    assert indexer.count_object_events("F150") == 7
    assert indexer.count_object_events("F150", activity="entering") == 2
    assert len(indexer.list_alerts("HIGH")) >= 3


def test_empty_search_and_overnight_time_range(monkeypatch) -> None:
    indexer = build_index(monkeypatch)

    assert indexer.search_text("!!!") == []
    frames = indexer.query_by_time("23:45", "00:01")
    assert {frame["id"] for frame in frames} == {"f001", "f002", "f049", "f050"}
