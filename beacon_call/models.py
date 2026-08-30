"""Data contracts shared by the camera API and LiveKit voice agent."""

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
    local_people_count: int = Field(default=1, ge=0, le=20)
    bbox: BoundingBox | None = None


class SceneAnalysis(BaseModel):
    people_count: int = Field(ge=0, le=20)
    scene_description: str = Field(min_length=1, max_length=500)


class Incident(BaseModel):
    id: str
    detected_at: str
    camera_name: str
    confidence: float
    frame_region: str
    summary: str
    status: Literal[
        "briefing_ready",
        "queued",
        "dialing",
        "answered",
        "acknowledged",
        "monitoring",
        "inspect",
        "failed",
        "timed_out",
    ]
    detector_people_count: int = Field(default=1, ge=0, le=20)
    people_count: int | None = Field(default=None, ge=0, le=20)
    scene_description: str | None = None
    analysis_status: Literal["pending", "complete", "failed"] = "pending"
    analysis_model: str | None = None
    evidence_url: str | None = None
    report_url: str | None = None
    call_id: str | None = None
    operator_name: str | None = None
    response: str | None = None
    simulation_id: str | None = None
    observed_state: str | None = None
    distance_m: float | None = Field(default=None, ge=0, le=10)
    idempotency_digest: str | None = None
    call_error: str | None = None

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


class EvidenceResult(BaseModel):
    incident: Incident
    analysis_error: str | None = None


class AppState(BaseModel):
    incident: Incident | None
    streak: int
    required_streak: int
    phone_number: str | None
    detector: str = "COCO-SSD trigger + OpenAI scene analysis"
    limitation: str = "Observable scene only — no identity, injury, or emergency diagnosis."


class OutboundIncidentRequest(BaseModel):
    """A bounded simulation incident that may initiate one outbound call."""

    simulation_id: str = Field(min_length=1, max_length=80)
    observed_state: Literal["motionless_adult_in_snow"] = "motionless_adult_in_snow"
    distance_m: float = Field(ge=0, le=10)
    camera_name: str = Field(default="G1-HEAD-CAM", min_length=1, max_length=40)


class OutboundIncidentResponse(BaseModel):
    incident: Incident
    duplicate: bool


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
