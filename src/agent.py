"""Question answering and daily summarization."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from src.indexer import Indexer
from src.providers import create_chat_model, provider_config
from src.tracker import Tracker


SYSTEM_PROMPT = (
    "You are a careful property drone security analyst. Use the supplied tools for "
    "questions about the patrol log. Do not invent events; report when the database "
    "has no matching evidence. Keep answers concise."
)


class AnalystAgent:
    """Provide deterministic offline intent routing and optional tool-calling Q&A."""

    def __init__(self, indexer: Indexer, tracker: Tracker | None = None) -> None:
        self.indexer = indexer
        self.tracker = tracker
        self._configuration = provider_config()
        self._model: Any = None
        self._tools: list[Any] | None = None
        self._history: list[Any] = []
        if self._configuration is not None:
            self._initialize_llm(self._configuration[0])

    def _initialize_llm(self, provider: str) -> None:
        from langchain_core.tools import tool

        @tool
        def query_by_time(start: str, end: str) -> str:
            """Find patrol frames between two clock times in HH:MM format."""
            return json.dumps(self.indexer.query_by_time(start, end))

        @tool
        def query_by_object(
            type: str = "", color: str = "", make: str = "", activity: str = ""
        ) -> str:
            """Find frames containing objects matching type, color, make, or activity."""
            return json.dumps(
                self.indexer.query_by_object(
                    type=type or None,
                    color=color or None,
                    make=make or None,
                    activity=activity or None,
                )
            )

        @tool
        def search_text(query: str) -> str:
            """Search the text descriptions attached to drone frames."""
            return json.dumps(self.indexer.search_text(query))

        @tool
        def count_events(label: str, activity: str = "") -> str:
            """Count detected object events, optionally limited to an activity."""
            return str(self.indexer.count_object_events(label, activity or None))

        @tool
        def list_alerts(severity: str = "") -> str:
            """List security alerts, optionally filtered by HIGH, MEDIUM, or LOW."""
            return json.dumps(self.indexer.list_alerts(severity or None))

        self._tools = [query_by_time, query_by_object, search_text, count_events, list_alerts]
        self._model = create_chat_model(provider).bind_tools(self._tools)

    def ask(self, question: str) -> str:
        if self._model is not None:
            return self._ask_with_llm(question)
        return self._ask_offline(question)

    def _ask_with_llm(self, question: str) -> str:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

        self._history.append(HumanMessage(content=question))
        messages = [SystemMessage(content=SYSTEM_PROMPT), *self._history]
        tool_map = {tool.name: tool for tool in self._tools or []}
        for _ in range(5):
            response = self._model.invoke(messages)
            messages.append(response)
            self._history.append(response)
            calls = getattr(response, "tool_calls", [])
            if not calls:
                return str(response.content)
            for call in calls:
                tool = tool_map.get(call["name"])
                if tool is None:
                    raise ValueError(f"LLM requested an unknown tool: {call['name']}")
                result = tool.invoke(call["args"])
                tool_message = ToolMessage(
                    content=str(result),
                    tool_call_id=call["id"],
                )
                messages.append(tool_message)
                self._history.append(tool_message)
        raise RuntimeError("LLM exceeded the maximum of five tool-calling rounds")

    @staticmethod
    def _is_night(ts: str) -> bool:
        clock = ts[11:16]
        return clock >= "22:00" or clock < "05:00"

    @staticmethod
    def _format_frames(frames: list[dict[str, Any]], limit: int = 20) -> str:
        if not frames:
            return "No matching events were found."
        lines = []
        for frame in frames[:limit]:
            labels = ", ".join(sorted({obj["label"] for obj in frame["objects"]}))
            detail = f" — {labels}" if labels else ""
            lines.append(
                f"{frame['ts'][11:16]} at {frame['zone']}{detail}: {frame['description']}"
            )
        if len(frames) > limit:
            lines.append(f"...and {len(frames) - limit} more matching frames.")
        return "\n".join(lines)

    def _ask_offline(self, question: str) -> str:
        normalized = question.lower()
        if ("alert" in normalized or "alerts" in normalized) and "night" in normalized:
            alerts = [
                alert
                for alert in self.indexer.list_alerts()
                if self._is_night(alert["ts"])
            ]
            if not alerts:
                return "There were no alerts at night."
            return "Night alerts:\n" + "\n".join(
                f"[{alert['severity']}] {alert['message']}" for alert in alerts
            )

        if (
            "how many" in normalized
            and ("f150" in normalized or "f-150" in normalized or "ford" in normalized)
            and any(word in normalized for word in ("enter", "entry", "entered"))
        ):
            count = self.indexer.count_object_events("F150", activity="entering")
            return f"The blue Ford F150 entered {count} times today."

        if "truck" in normalized and any(word in normalized for word in ("show", "list", "all")):
            frames = self.indexer.query_by_object(type="truck")
            return self._format_frames(frames)

        time_range = re.search(
            r"between\s+(\d{1,2}:\d{2})\s+and\s+(\d{1,2}:\d{2})", normalized
        )
        if time_range:
            frames = self.indexer.query_by_time(*time_range.groups())
            return self._format_frames(frames)

        if "object" in normalized or "video" in normalized:
            frames = self.indexer.query_by_object()
            counts: Counter[str] = Counter()
            for frame in frames:
                counts.update(obj["label"] for obj in frame["objects"])
            if not counts:
                return "No objects were detected in the video."
            return "Objects detected: " + "; ".join(
                f"{label} ({count} detections)" for label, count in sorted(counts.items())
            )

        terms = re.sub(
            r"\b(show|find|search|what|where|when|please|the|all|events?)\b",
            " ",
            normalized,
        ).strip()
        return self._format_frames(self.indexer.search_text(terms))

    def summarize_day(self) -> str:
        frames = self.indexer.query_by_object()
        labels: Counter[str] = Counter()
        for frame in frames:
            labels.update(obj["label"] for obj in frame["objects"])
        alerts = self.indexer.list_alerts()
        object_events = sum(labels.values())
        first = (
            f"Today's patrol processed {self.tracker.frame_count} frames, recorded "
            f"{object_events} object detections, and raised {len(alerts)} alerts."
            if self.tracker
            else f"Today's patrol recorded {object_events} object detections and raised {len(alerts)} alerts."
        )
        bullets = []
        bullets.extend(
            f"- {label}: {count} detections"
            for label, count in sorted(labels.items())
        )
        if alerts:
            bullets.append(f"- Alerts: {len(alerts)} total ({', '.join(sorted({a['severity'] for a in alerts}))})")
        else:
            bullets.append("- Alerts: none")
        return first + "\n" + "\n".join(bullets)
