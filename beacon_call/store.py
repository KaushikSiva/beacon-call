"""Small local incident store shared by the camera API and voice Expert."""

from __future__ import annotations

import logging
import os
import threading
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from beacon_call.models import BoundingBox, Incident, SceneAnalysis, utc_now_iso
from beacon_call.reports import generate_incident_report

logger = logging.getLogger("beacon_call.store")


def frame_region(box: BoundingBox | None) -> str:
    if box is None:
        return "unknown area"
    center = (box.x + box.width / 2) / box.frame_width
    if center < 0.34:
        return "left side"
    if center > 0.66:
        return "right side"
    return "center"


class IncidentStore:
    def __init__(self, runtime_dir: Path):
        self.runtime_dir = runtime_dir
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir = self.runtime_dir / "evidence"
        self.report_dir = self.runtime_dir / "reports"
        self.incident_dir = self.runtime_dir / "incidents"
        self.latest_path = self.runtime_dir / "latest-incident.json"
        self._lock = threading.RLock()

    @classmethod
    def from_environment(cls) -> IncidentStore:
        project_dir = Path(__file__).resolve().parent.parent
        configured = os.environ.get("BEACON_RUNTIME_DIR", "runtime")
        runtime_dir = Path(configured)
        if not runtime_dir.is_absolute():
            runtime_dir = project_dir / runtime_dir
        return cls(runtime_dir)

    def latest(self) -> Incident | None:
        with self._lock:
            if not self.latest_path.exists():
                return None
            return Incident.model_validate_json(self.latest_path.read_text())

    def create(
        self,
        *,
        camera_name: str,
        confidence: float,
        bbox: BoundingBox | None,
        detector_people_count: int = 1,
    ) -> Incident:
        region = frame_region(bbox)
        incident = Incident(
            id=f"BC-{uuid4().hex[:8].upper()}",
            detected_at=utc_now_iso(),
            camera_name=camera_name,
            confidence=confidence,
            frame_region=region,
            summary=(
                f"At least one person triggered the local detector on the {region} of "
                f"{camera_name}. OpenAI scene analysis is pending."
            ),
            status="briefing_ready",
            detector_people_count=max(0, detector_people_count),
        )
        self._write(incident)
        return incident

    def create_outbound(
        self,
        *,
        idempotency_key: str,
        simulation_id: str,
        observed_state: str,
        distance_m: float,
        camera_name: str,
    ) -> tuple[Incident, bool]:
        """Create one incident per idempotency key, including across restarts."""

        digest = sha256(idempotency_key.encode("utf-8")).hexdigest()
        with self._lock:
            existing = self.find_by_idempotency_digest(digest)
            if existing is not None:
                return existing, True
            incident = Incident(
                id=f"BC-{uuid4().hex[:8].upper()}",
                detected_at=utc_now_iso(),
                camera_name=camera_name,
                confidence=1.0,
                frame_region="robot proximity envelope",
                summary=(
                    "Everest G1 reached a motionless adult lying in snow. "
                    "Responsiveness and vital signs are unknown."
                ),
                status="queued",
                detector_people_count=1,
                people_count=1,
                scene_description=(
                    "One motionless adult is lying in snow within the robot's bounded "
                    "proximity envelope. Responsiveness and vital signs are unknown."
                ),
                analysis_status="complete",
                analysis_model="simulation-ground-truth",
                simulation_id=simulation_id,
                observed_state=observed_state,
                distance_m=distance_m,
                idempotency_digest=digest,
            )
            self._write_with_report(incident)
            return incident, False

    def get(self, incident_id: str) -> Incident | None:
        with self._lock:
            path = self.incident_dir / f"{incident_id}.json"
            if path.exists():
                return Incident.model_validate_json(path.read_text())
            latest = self.latest()
            if latest is not None and latest.id == incident_id:
                return latest
            return None

    def find_by_idempotency_digest(self, digest: str) -> Incident | None:
        with self._lock:
            if not self.incident_dir.exists():
                return None
            for path in self.incident_dir.glob("BC-*.json"):
                incident = Incident.model_validate_json(path.read_text())
                if incident.idempotency_digest == digest:
                    return incident
            return None

    def record_call_status(
        self,
        incident_id: str,
        *,
        status: str,
        call_id: str | None = None,
        error: str | None = None,
    ) -> Incident:
        allowed = {"queued", "dialing", "answered", "failed", "timed_out"}
        if status not in allowed:
            raise ValueError(f"Unsupported call status: {status}")
        with self._lock:
            incident = self._require(incident_id)
            incident.status = status  # type: ignore[assignment]
            if call_id is not None:
                incident.call_id = call_id
            incident.call_error = error
            self._write_with_report(incident)
            return incident

    def attach_evidence(self, incident_id: str, jpeg_bytes: bytes) -> Incident:
        with self._lock:
            incident = self._require(incident_id)
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            path = self.evidence_dir / f"{incident.id}.jpg"
            path.write_bytes(jpeg_bytes)
            incident.evidence_url = f"/api/evidence/{incident.id}.jpg"
            self._write(incident)
            return incident

    def record_scene_analysis(
        self, incident_id: str, *, analysis: SceneAnalysis, model: str
    ) -> Incident:
        with self._lock:
            incident = self._require(incident_id)
            noun = "person" if analysis.people_count == 1 else "people"
            incident.people_count = analysis.people_count
            incident.scene_description = analysis.scene_description
            incident.analysis_status = "complete"
            incident.analysis_model = model
            incident.summary = (
                f"OpenAI vision counted {analysis.people_count} {noun}. "
                f"{analysis.scene_description} Observable scene only; condition unknown."
            )
            self._write_with_report(incident)
            return incident

    def record_analysis_failure(self, incident_id: str) -> Incident:
        with self._lock:
            incident = self._require(incident_id)
            incident.analysis_status = "failed"
            incident.summary = (
                f"The local detector saw at least one person in the {incident.frame_region}. "
                "OpenAI scene analysis was unavailable; human review is required."
            )
            self._write_with_report(incident)
            return incident

    def record_call_outcome(
        self, incident_id: str, *, call_id: str, operator_name: str, response: str
    ) -> Incident:
        with self._lock:
            incident = self._require(incident_id)
            status_map = {
                "acknowledged": "acknowledged",
                "continue monitoring": "monitoring",
                "inspect camera feed": "inspect",
            }
            normalized_response = response.strip().lower()
            incident.status = status_map.get(normalized_response, "acknowledged")
            incident.call_id = call_id
            incident.operator_name = operator_name
            incident.response = normalized_response
            self._write_with_report(incident)
            return incident

    def reset(self) -> None:
        with self._lock:
            self.latest_path.unlink(missing_ok=True)

    def _require(self, incident_id: str) -> Incident:
        incident = self.get(incident_id)
        if incident is None:
            raise KeyError(incident_id)
        return incident

    def _write(self, incident: Incident) -> None:
        with self._lock:
            self.incident_dir.mkdir(parents=True, exist_ok=True)
            incident_path = self.incident_dir / f"{incident.id}.json"
            incident_temp = incident_path.with_suffix(".tmp")
            incident_temp.write_text(incident.model_dump_json(indent=2))
            incident_temp.replace(incident_path)
            temp_path = self.latest_path.with_suffix(".tmp")
            temp_path.write_text(incident.model_dump_json(indent=2))
            temp_path.replace(self.latest_path)

    def _write_with_report(self, incident: Incident) -> None:
        incident.report_url = f"/api/reports/{incident.id}.pdf"
        self._write(incident)
        try:
            generate_incident_report(incident, self.report_dir / f"{incident.id}.pdf")
        except Exception:
            logger.exception("Could not generate report for %s", incident.id)
