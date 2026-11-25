"""End-to-end scenario tests."""

from datetime import datetime

from src.indexer import Indexer
from src.models import Frame, Telemetry
from src.simulator import load_scenario, stream_frames
from main import run_pipeline


def test_full_scenario_logs_frames_alerts_and_objects(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    indexer = Indexer(tmp_path / "scenario.db")
    output: list[str] = []
    tracker, alerts = run_pipeline(
        indexer,
        output=output.append,
        alert_log_path=tmp_path / "alerts.log",
    )

    assert tracker.frame_count == 50
    assert indexer.connection.execute("SELECT COUNT(*) FROM frames").fetchone()[0] == 50
    assert [
        (alert.rule, alert.timestamp.strftime("%H:%M"), alert.severity)
        for alert in alerts
    ] == [
        ("NIGHT_PERSON", "00:01", "HIGH"),
        ("LOITERING", "00:01", "HIGH"),
        ("NIGHT_PERSON", "02:30", "HIGH"),
        ("TELEMETRY_ALTITUDE", "11:30", "MEDIUM"),
        ("TELEMETRY_BATTERY", "16:00", "MEDIUM"),
        ("REPEAT_ENTRY", "18:20", "LOW"),
        ("UNKNOWN_VEHICLE_NIGHT", "23:15", "MEDIUM"),
    ]
    assert any("Blue Ford F150 truck spotted at garage, 12:00." in line for line in output)
    assert any("[HIGH] Person loitering at main_gate, 00:01" == line for line in output)
    assert indexer.connection.execute(
        "SELECT COUNT(*) FROM alerts WHERE frame_id = 'f029'"
    ).fetchone()[0] == 0
    assert (tmp_path / "alerts.log").read_text(encoding="utf-8").count("\n") == len(alerts)
    indexer.close()


def test_out_of_order_frames_are_replayed_in_time_order() -> None:
    later = Frame(
        "later",
        datetime(2025, 1, 15, 1, 0),
        Telemetry("garage", 0.0, 0.0, 30, 80, 2),
        "Empty garage.",
    )
    earlier = Frame(
        "earlier",
        datetime(2025, 1, 15, 0, 0),
        Telemetry("main_gate", 0.0, 0.0, 30, 80, 2),
        "Empty gate.",
    )

    assert [frame.frame_id for frame in stream_frames([later, earlier])] == [
        "earlier",
        "later",
    ]
    assert len(load_scenario()) == 50
