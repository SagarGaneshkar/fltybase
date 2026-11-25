"""Object extraction from text-described simulated frames."""

from __future__ import annotations

import re

from src.models import DetectedObject, Frame
from src.providers import create_chat_model, provider_config


_OBJECT_PATTERN = re.compile(
    r"\b(person|people|pedestrian|dog|cat|bird|vehicle|car|truck|van|sedan|"
    r"pickup|ford\s*f[\s-]?150)\b",
    re.IGNORECASE,
)
_COLORS = ("blue", "red", "white", "black", "gray", "grey", "silver", "brown")


def _activity(description: str) -> str:
    lowered = description.lower()
    for activity in (
        "entering",
        "loitering",
        "parked",
        "walking",
        "leaving",
        "departing",
        "driving",
        "stopped",
        "crossing",
        "sniffing",
    ):
        if re.search(rf"\b{activity}\b", lowered):
            return activity
    return "observed"


def _extract_with_rules(frame: Frame) -> list[DetectedObject]:
    """Extract recognizable entities from the simulated text description."""
    description = re.sub(
        r"\bno\s+(?:people|persons?|pedestrians?|vehicles?|cars?|trucks?|vans?|"
        r"sedans?|pickups?|dogs?|cats?|birds?)(?:\s+or\s+(?:people|persons?|"
        r"pedestrians?|vehicles?|cars?|trucks?|vans?|sedans?|pickups?|dogs?|cats?|birds?))*\b",
        "",
        frame.description.strip(),
        flags=re.IGNORECASE,
    )
    if not description or not _OBJECT_PATTERN.search(description):
        return []

    lowered = description.lower()
    color = next((name for name in _COLORS if re.search(rf"\b{name}\b", lowered)), None)
    activity = _activity(description)
    found: list[DetectedObject] = []

    if re.search(r"\b(person|people|pedestrian)\b", lowered):
        found.append(
            DetectedObject(
                type="person",
                color=color,
                make_model=None,
                activity=activity,
                zone=frame.telemetry.zone,
                label="person",
            )
        )

    animal = next(
        (name for name in ("dog", "cat", "bird") if re.search(rf"\b{name}\b", lowered)),
        None,
    )
    if animal:
        found.append(
            DetectedObject(
                type="animal",
                color=color,
                make_model=animal,
                activity=activity,
                zone=frame.telemetry.zone,
                label=f"{color + ' ' if color else ''}{animal}",
            )
        )

    vehicle_found = bool(
        re.search(r"\b(vehicle|car|truck|van|sedan|pickup|ford\s*f[\s-]?150)\b", lowered)
    )
    if vehicle_found:
        if re.search(r"\bford\s*f[\s-]?150\b", lowered):
            make_model = "Ford F150"
            vehicle_kind = "truck"
        elif "delivery van" in lowered:
            make_model = "delivery van"
            vehicle_kind = "van"
        elif re.search(r"\bsedan\b", lowered):
            make_model = "sedan"
            vehicle_kind = "sedan"
        elif re.search(r"\bvan\b", lowered):
            make_model = "van"
            vehicle_kind = "van"
        elif re.search(r"\btruck\b", lowered):
            make_model = "truck"
            vehicle_kind = "truck"
        elif re.search(r"\bpickup\b", lowered):
            make_model = "pickup"
            vehicle_kind = "truck"
        else:
            make_model = "vehicle"
            vehicle_kind = "vehicle"
        prefix = "unknown " if "unknown" in lowered else ""
        vehicle_label = (
            f"{prefix}{color + ' ' if color else ''}{make_model}"
            f"{' truck' if vehicle_kind == 'truck' and make_model == 'Ford F150' else ''}"
        )
        found.append(
            DetectedObject(
                type="vehicle",
                color=color,
                make_model=make_model,
                activity=activity,
                zone=frame.telemetry.zone,
                label=vehicle_label,
            )
        )
    return found


def _extract_with_llm(frame: Frame, provider: str) -> list[DetectedObject]:
    # The structured extractor below was AI-assisted; the deterministic parser keeps offline runs reproducible.
    from pydantic import BaseModel, Field

    class ObjectPayload(BaseModel):
        type: str
        color: str | None = None
        make_model: str | None = None
        activity: str = "observed"
        label: str

    class DetectionPayload(BaseModel):
        objects: list[ObjectPayload] = Field(default_factory=list)

    structured_model = create_chat_model(provider).with_structured_output(DetectionPayload)
    result = structured_model.invoke(
        "Extract only visible entities from the text. Allowed types: person, vehicle, "
        "animal, other. Use concise labels and do not infer unseen details.\n"
        f"Zone: {frame.telemetry.zone}\nDescription: {frame.description}"
    )
    valid_types = {"person", "vehicle", "animal", "other"}
    objects: list[DetectedObject] = []
    for item in result.objects:
        if item.type not in valid_types:
            continue
        objects.append(
            DetectedObject(
                type=item.type,
                color=item.color,
                make_model=item.make_model,
                activity=item.activity,
                zone=frame.telemetry.zone,
                label=item.label,
            )
        )
    return objects


def detect_objects(frame: Frame) -> list[DetectedObject]:
    """Automatically use a configured LangChain LLM, otherwise deterministic rules."""
    configuration = provider_config()
    if configuration is None:
        return _extract_with_rules(frame)
    provider, _ = configuration
    return _extract_with_llm(frame, provider)
