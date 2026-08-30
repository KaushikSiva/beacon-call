"""FastAPI surface for the Mac camera console."""

from __future__ import annotations

import base64
import binascii
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError

from beacon_call.auth import require_api_token
from beacon_call.livekit_service import place_incident_call
from beacon_call.models import (
    AppState,
    DetectionResult,
    EvidencePayload,
    EvidenceResult,
    Observation,
    OutboundIncidentRequest,
    OutboundIncidentResponse,
)
from beacon_call.scene import SceneAnalysisError, analyze_scene
from beacon_call.store import IncidentStore
from beacon_call.vision_gate import PresenceGate

PROJECT_DIR = Path(__file__).resolve().parent.parent
WEB_DIST = PROJECT_DIR / "web-dist"
load_dotenv(PROJECT_DIR / ".env")
logger = logging.getLogger("beacon_call.api")
store = IncidentStore.from_environment()
gate = PresenceGate()

app = FastAPI(
    title="BeaconCall",
    description="Robot-camera incidents with LiveKit and Twilio outbound voice acknowledgment.",
    version="0.2.0",
)


def app_state() -> AppState:
    return AppState(
        incident=store.latest(),
        streak=gate.streak,
        required_streak=gate.required_hits,
        phone_number=None,
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    agent_health_url = os.environ.get("BEACON_AGENT_HEALTH_URL", "").strip()
    voice_worker = "not_checked"
    if agent_health_url:
        try:
            with urllib.request.urlopen(agent_health_url, timeout=1.0) as response:
                if response.status != 200:
                    raise RuntimeError(f"LiveKit worker health returned {response.status}")
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            raise HTTPException(status_code=503, detail="LiveKit worker is not ready") from exc
        voice_worker = "ready"
    return {"status": "ok", "service": "beacon-call", "voice_worker": voice_worker}


@app.get("/api/state", response_model=AppState)
def get_state() -> AppState:
    return app_state()


@app.post("/api/observations", response_model=DetectionResult)
def observe(observation: Observation) -> DetectionResult:
    created = gate.observe(
        person_present=observation.person_present,
        confidence=observation.confidence,
    )
    incident = store.latest()
    if created:
        incident = store.create(
            camera_name=observation.camera_name,
            confidence=observation.confidence,
            bbox=observation.bbox,
            detector_people_count=observation.local_people_count,
        )
    return DetectionResult(
        streak=gate.streak,
        required_streak=gate.required_hits,
        created=created,
        incident=incident,
    )


async def _run_outbound_call(incident_id: str) -> None:
    try:
        incident = store.record_call_status(incident_id, status="dialing")
        placement = await place_incident_call(incident)
        store.record_call_status(
            incident_id,
            status="answered",
            call_id=placement.participant_id or placement.room_name,
        )
    except Exception as exc:
        logger.exception("Outbound call failed for incident %s", incident_id)
        try:
            store.record_call_status(
                incident_id,
                status="failed",
                error=f"{type(exc).__name__}: outbound call failed",
            )
        except Exception:
            logger.exception("Could not persist outbound failure for %s", incident_id)


@app.post(
    "/api/incidents/outbound-call",
    response_model=OutboundIncidentResponse,
    status_code=202,
    dependencies=[Depends(require_api_token)],
)
async def outbound_incident_call(
    payload: OutboundIncidentRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> OutboundIncidentResponse:
    if not idempotency_key or not (8 <= len(idempotency_key) <= 200):
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key must contain between 8 and 200 characters",
        )
    incident, duplicate = store.create_outbound(
        idempotency_key=idempotency_key,
        simulation_id=payload.simulation_id,
        observed_state=payload.observed_state,
        distance_m=payload.distance_m,
        camera_name=payload.camera_name,
    )
    if not duplicate:
        background_tasks.add_task(_run_outbound_call, incident.id)
    return OutboundIncidentResponse(
        incident=incident.model_copy(update={"idempotency_digest": None}),
        duplicate=duplicate,
    )


@app.post("/api/incidents/{incident_id}/evidence", response_model=EvidenceResult)
def attach_evidence(incident_id: str, payload: EvidencePayload) -> EvidenceResult:
    prefix = "data:image/jpeg;base64,"
    if not payload.image_data_url.startswith(prefix):
        raise HTTPException(status_code=400, detail="Expected a JPEG data URL")
    try:
        jpeg_bytes = base64.b64decode(payload.image_data_url[len(prefix) :], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image") from exc
    if len(jpeg_bytes) > 2_000_000:
        raise HTTPException(status_code=413, detail="Evidence frame exceeds 2 MB")
    try:
        incident = store.attach_evidence(incident_id, jpeg_bytes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Incident not found") from exc

    analysis_error = None
    try:
        analysis, model = analyze_scene(jpeg_bytes)
        incident = store.record_scene_analysis(incident_id, analysis=analysis, model=model)
    except SceneAnalysisError as exc:
        logger.warning("OpenAI scene analysis unavailable: %s", exc)
        incident = store.record_analysis_failure(incident_id)
        analysis_error = str(exc)
    except (OpenAIError, ValueError) as exc:
        logger.warning("OpenAI scene analysis failed: %s", type(exc).__name__)
        incident = store.record_analysis_failure(incident_id)
        analysis_error = "OpenAI scene analysis failed; check the API key and model access"
    return EvidenceResult(incident=incident, analysis_error=analysis_error)


@app.get("/api/evidence/{filename}")
def evidence(filename: str) -> FileResponse:
    if not filename.endswith(".jpg") or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid evidence filename")
    path = store.evidence_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/reports/{filename}")
def report(filename: str) -> FileResponse:
    if not filename.endswith(".pdf") or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid report filename")
    path = store.report_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/demo/reset", response_model=AppState)
def reset_demo() -> AppState:
    gate.reset()
    store.reset()
    return app_state()


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")


@app.get("/", response_class=HTMLResponse)
def index() -> Response:
    index_path = WEB_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path, headers={"Cache-Control": "no-store"})
    return HTMLResponse(
        "<h1>BeaconCall UI is not built</h1><p>Run <code>npm install && npm run build</code>.</p>",
        status_code=503,
    )
