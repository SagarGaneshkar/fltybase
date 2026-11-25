"""CLI entry point for the Drone Security Analyst Agent."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Callable

from src.agent import AnalystAgent
from src.alert_engine import AlertEngine
from src.detector import detect_objects
from src.indexer import Indexer
from src.models import Alert
from src.simulator import load_scenario, stream_frames
from src.tracker import Tracker


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "drone_security.db"
DEFAULT_ALERT_LOG = PROJECT_ROOT / "data" / "alerts.log"


def _load_dotenv() -> None:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                name, value = stripped.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def _database_path() -> Path:
    value = os.getenv("DRONE_DB_PATH")
    return Path(value) if value else DEFAULT_DATABASE


def run_pipeline(
    indexer: Indexer,
    speed: float = 0.0,
    output: Callable[[str], None] = print,
    alert_log_path: str | Path | None = None,
    on_frame: Callable[[int, int], None] | None = None,
) -> tuple[Tracker, list[Alert]]:
    """Replay the configured scenario through detection, tracking, alerts, and storage."""
    tracker = Tracker()
    alert_engine = AlertEngine()
    all_alerts: list[Alert] = []
    log_file = None
    if alert_log_path is not None:
        log_path = Path(alert_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("w", encoding="utf-8")
    try:
        frames = load_scenario()
        for frame_number, frame in enumerate(stream_frames(frames, speed=speed), start=1):
            objects = detect_objects(frame)
            current_states = tracker.update(frame, objects)
            alerts = alert_engine.evaluate(frame, objects, current_states)
            indexer.add_frame(frame, objects, alerts)
            for obj in objects:
                label = obj.label[0].upper() + obj.label[1:] if obj.label else obj.label
                output(f"{label} spotted at {obj.zone}, {frame.timestamp:%H:%M}.")
            for alert in alerts:
                line = f"[{alert.severity}] {alert.message}"
                output(line)
                if log_file:
                    log_file.write(line + "\n")
                    log_file.flush()
                all_alerts.append(alert)
            if on_frame is not None:
                on_frame(frame_number, len(frames))
    finally:
        if log_file:
            log_file.close()
    return tracker, all_alerts


def _print_frames(frames: list[dict[str, object]]) -> None:
    print(AnalystAgent._format_frames(frames))


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Drone Security Analyst Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Replay and process the day scenario")
    run_parser.add_argument("--speed", type=float, default=0.0, help="Replay speed multiplier")

    query_parser = subparsers.add_parser("query", help="Query indexed patrol data")
    query_group = query_parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--object", dest="object_query")
    query_group.add_argument("--time", dest="time_range", help="Clock range, for example 00:00-01:00")
    query_group.add_argument("--text", dest="text_query")

    ask_parser = subparsers.add_parser("ask", help="Ask the analyst a question")
    ask_parser.add_argument("question", nargs="?")

    subparsers.add_parser("summary", help="Summarize the indexed patrol")
    caption_parser = subparsers.add_parser("caption", help="Optional BLIP caption for an image")
    caption_parser.add_argument("image_path")
    ui_parser = subparsers.add_parser("ui", help="Open the interactive browser dashboard")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8765)
    return parser


def _run_cli(args: argparse.Namespace) -> int:
    if args.command == "caption":
        from src.vlm_caption import caption_images

        for image_path, caption in caption_images([args.image_path]):
            print(f"{image_path}: {caption}")
        return 0
    if args.command == "ui":
        from src.web_ui import serve

        serve(host=args.host, port=args.port)
        return 0

    indexer = Indexer(_database_path())
    try:
        if args.command == "run":
            run_pipeline(
                indexer,
                speed=args.speed,
                alert_log_path=DEFAULT_ALERT_LOG,
            )
        elif args.command == "query":
            if args.object_query:
                query = args.object_query.strip()
                if query.lower() in {"person", "vehicle", "animal", "other", "truck", "van", "car", "sedan"}:
                    frames = indexer.query_by_object(type=query)
                elif query.lower() in {"blue", "red", "white", "black", "gray", "grey", "silver", "brown"}:
                    frames = indexer.query_by_object(color=query)
                else:
                    frames = indexer.query_by_object(make=query)
                _print_frames(frames)
            elif args.time_range:
                parts = args.time_range.split("-", maxsplit=1)
                if len(parts) != 2:
                    raise ValueError("Time range must use HH:MM-HH:MM format")
                _print_frames(indexer.query_by_time(parts[0], parts[1]))
            else:
                _print_frames(indexer.search_text(args.text_query))
        elif args.command == "ask":
            agent = AnalystAgent(indexer)
            if args.question:
                print(agent.ask(args.question))
            else:
                print("Ask about the patrol log. Type 'exit' to end.")
                while True:
                    try:
                        question = input("You: ").strip()
                    except EOFError:
                        break
                    if question.lower() in {"exit", "quit"}:
                        break
                    if question:
                        print(f"Analyst: {agent.ask(question)}")
        elif args.command == "summary":
            print(AnalystAgent(indexer).summarize_day())
    finally:
        indexer.close()
    return 0


def main() -> int:
    _load_dotenv()
    parser = _make_parser()
    args = parser.parse_args(["ui"] if len(os.sys.argv) == 1 else None)
    return _run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
