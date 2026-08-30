"""FastAPI surface for the Mac camera console."""

from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from beacon_call.models import AppState, DetectionResult, EvidencePayload, Observation
from beacon_call.store import IncidentStore
from beacon_call.vision_gate import PresenceGate

PROJECT_DIR = Path(__file__).resolve().parent.parent
WEB_DIST = PROJECT_DIR / "web-dist"
load_dotenv(PROJECT_DIR / ".env")
store = IncidentStore.from_environment()
gate = PresenceGate()

app = FastAPI(
    title="BeaconCall",
    description="Presence-only camera events for a Guava inbound voice briefing.",
    version="0.1.0",
)


def app_state() -> AppState:
    return AppState(
        incident=store.latest(),
        streak=gate.streak,
        required_streak=gate.required_hits,
        phone_number=os.environ.get("GUAVA_AGENT_NUMBER"),
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "beacon-call"}


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
        )
    return DetectionResult(
        streak=gate.streak,
        required_streak=gate.required_hits,
        created=created,
        incident=incident,
    )


@app.post("/api/incidents/{incident_id}/evidence")
def attach_evidence(incident_id: str, payload: EvidencePayload) -> dict[str, object]:
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
    return {"incident": incident}


@app.get("/api/evidence/{filename}")
def evidence(filename: str) -> FileResponse:
    if not filename.endswith(".jpg") or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid evidence filename")
    path = store.evidence_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


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
