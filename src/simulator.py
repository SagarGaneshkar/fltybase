"""Scenario loading and ordered frame replay."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterator

from src.models import Frame


DEFAULT_SCENARIO = Path(__file__).resolve().parents[1] / "data" / "scenario_day1.json"


def load_scenario(path: str | Path = DEFAULT_SCENARIO) -> list[Frame]:
    """Load and chronologically sort frames from a JSON scenario."""
    scenario_path = Path(path)
    with scenario_path.open(encoding="utf-8") as scenario_file:
        raw_frames = json.load(scenario_file)
    if not isinstance(raw_frames, list):
        raise ValueError(f"Scenario must be a JSON list: {scenario_path}")
    frames = [Frame.from_dict(item) for item in raw_frames]
    return sorted(frames, key=lambda frame: frame.timestamp)


def stream_frames(
    frames: list[Frame], speed: float = 0.0
) -> Iterator[Frame]:
    """Yield frames in time order; positive speed scales replay delays."""
    if speed < 0:
        raise ValueError("speed must be non-negative")
    ordered_frames = sorted(frames, key=lambda frame: frame.timestamp)
    previous_timestamp = None
    for frame in ordered_frames:
        if speed > 0 and previous_timestamp is not None:
            delay = (frame.timestamp - previous_timestamp).total_seconds() / speed
            time.sleep(max(delay, 0.0))
        yield frame
        previous_timestamp = frame.timestamp
