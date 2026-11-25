"""Agent question-answering tests."""

import pytest

from src.agent import AnalystAgent
from src.alert_engine import AlertEngine
from src.detector import detect_objects
from src.indexer import Indexer
from src.simulator import load_scenario
from src.tracker import Tracker


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    indexer = Indexer()
    tracker = Tracker()
    alert_engine = AlertEngine()
    for frame in load_scenario():
        objects = detect_objects(frame)
        states = tracker.update(frame, objects)
        indexer.add_frame(frame, objects, alert_engine.evaluate(frame, objects, states))
    return AnalystAgent(indexer, tracker)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What objects were in the video?", "blue Ford F150 truck"),
        ("How many times did the F150 enter today?", "entered 2 times"),
        ("Show all truck events", "Ford F150"),
        ("Any alerts at night?", "Night alerts:"),
        ("What happened between 00:00 and 01:00?", "00:01 at main_gate"),
    ],
)
def test_agent_answers_required_questions(agent, question, expected) -> None:
    assert expected.lower() in agent.ask(question).lower()


def test_summary_has_one_sentence_and_bullet_recap(agent) -> None:
    summary = agent.summarize_day()

    assert summary.startswith("Today's patrol processed 50 frames")
    assert "\n- " in summary
