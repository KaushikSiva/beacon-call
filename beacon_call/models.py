"""Data contracts shared by the camera API and Guava Expert."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    frame_width: float = Field(gt=0)
    frame_height: float = Field(gt=0)


class Observation(BaseModel):
    person_present: bool
    confidence: float = Field(default=0, ge=0, le=1)
    camera_name: str = Field(default="MAC-01", min_length=1, max_length=40)
    bbox: BoundingBox | None = None


class Incident(BaseModel):
    id: str
    detected_at: str
    camera_name: str
    confidence: float
    frame_region: str
    summary: str
    status: Literal["awaiting_inbound_call", "acknowledged", "monitoring", "inspect"]
    evidence_url: str | None = None
    call_id: str | None = None
    operator_name: str | None = None
    response: str | None = None

    @property
    def confidence_percent(self) -> int:
        return round(self.confidence * 100)

    @property
    def detected_at_display(self) -> str:
        parsed = datetime.fromisoformat(self.detected_at)
        return parsed.astimezone().strftime("%I:%M %p").lstrip("0")


class DetectionResult(BaseModel):
    streak: int
    required_streak: int
    created: bool
    incident: Incident | None


class EvidencePayload(BaseModel):
    image_data_url: str = Field(min_length=20, max_length=3_000_000)


class AppState(BaseModel):
    incident: Incident | None
    streak: int
    required_streak: int
    phone_number: str | None
    detector: str = "COCO-SSD / MobileNet v2"
    limitation: str = "Presence only — no fall, injury, identity, or emergency inference."


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
