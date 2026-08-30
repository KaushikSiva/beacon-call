import base64
from pathlib import Path

from fastapi.testclient import TestClient

from beacon_call import api
from beacon_call.livekit_service import CallPlacement
from beacon_call.models import SceneAnalysis
from beacon_call.scene import SceneAnalysisError
from beacon_call.store import IncidentStore
from beacon_call.vision_gate import PresenceGate


def setup_api(tmp_path: Path) -> TestClient:
    api.store = IncidentStore(tmp_path)
    api.gate = PresenceGate(required_hits=3, threshold=0.66, cooldown_seconds=20)
    return TestClient(api.app)


def test_health_requires_configured_livekit_worker_readiness(tmp_path: Path, monkeypatch) -> None:
    client = setup_api(tmp_path)
    monkeypatch.delenv("BEACON_AGENT_HEALTH_URL", raising=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["voice_worker"] == "not_checked"

    class HealthyWorker:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    monkeypatch.setenv("BEACON_AGENT_HEALTH_URL", "http://127.0.0.1:8081/")
    monkeypatch.setattr(api.urllib.request, "urlopen", lambda *_args, **_kwargs: HealthyWorker())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["voice_worker"] == "ready"

    def unavailable(*_args, **_kwargs):
        raise OSError("worker unavailable")

    monkeypatch.setattr(api.urllib.request, "urlopen", unavailable)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "LiveKit worker is not ready"}


def test_observations_create_one_incident_after_three_hits(tmp_path: Path) -> None:
    client = setup_api(tmp_path)
    payload = {
        "person_present": True,
        "confidence": 0.88,
        "camera_name": "MAC-01",
        "bbox": {
            "x": 200,
            "y": 20,
            "width": 100,
            "height": 220,
            "frame_width": 640,
            "frame_height": 480,
        },
    }
    assert client.post("/api/observations", json=payload).json()["created"] is False
    assert client.post("/api/observations", json=payload).json()["created"] is False
    response = client.post("/api/observations", json=payload)
    assert response.status_code == 200
    assert response.json()["created"] is True
    assert response.json()["incident"]["frame_region"] == "center"


def test_reset_clears_incident(tmp_path: Path) -> None:
    client = setup_api(tmp_path)
    api.store.create(camera_name="MAC-01", confidence=0.90, bbox=None)
    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    assert response.json()["incident"] is None


def test_evidence_runs_openai_scene_analysis_and_creates_pdf(tmp_path: Path, monkeypatch) -> None:
    client = setup_api(tmp_path)
    incident = api.store.create(
        camera_name="MAC-01",
        confidence=0.90,
        bbox=None,
        detector_people_count=1,
    )

    def fake_analyze(_: bytes) -> tuple[SceneAnalysis, str]:
        return (
            SceneAnalysis(
                people_count=2,
                scene_description="Two people are standing side by side in an indoor room.",
            ),
            "gpt-5.6-luna",
        )

    monkeypatch.setattr(api, "analyze_scene", fake_analyze)
    jpeg = base64.b64encode(b"\xff\xd8" + b"camera-frame" * 4 + b"\xff\xd9").decode()
    response = client.post(
        f"/api/incidents/{incident.id}/evidence",
        json={"image_data_url": f"data:image/jpeg;base64,{jpeg}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["incident"]["people_count"] == 2
    assert payload["incident"]["analysis_status"] == "complete"

    report = client.get(payload["incident"]["report_url"])
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert report.content.startswith(b"%PDF")


def test_outbound_call_requires_authentication(tmp_path: Path, monkeypatch) -> None:
    client = setup_api(tmp_path)
    monkeypatch.setenv("BEACON_API_TOKEN", "test-secret")
    response = client.post(
        "/api/incidents/outbound-call",
        headers={"Idempotency-Key": "episode-001"},
        json={"simulation_id": "sim-001", "distance_m": 0.4},
    )
    assert response.status_code == 401


def test_outbound_call_dispatches_once_and_hides_destination(tmp_path: Path, monkeypatch) -> None:
    client = setup_api(tmp_path)
    monkeypatch.setenv("BEACON_API_TOKEN", "test-secret")
    calls: list[str] = []

    async def fake_place(incident):
        calls.append(incident.id)
        return CallPlacement(
            room_name=f"beacon-{incident.id.lower()}",
            participant_identity="responder-test",
            participant_id="PA_test",
        )

    monkeypatch.setattr(api, "place_incident_call", fake_place)
    headers = {
        "Authorization": "Bearer test-secret",
        "Idempotency-Key": "episode-everest-001",
    }
    body = {
        "simulation_id": "everest-001",
        "observed_state": "motionless_adult_in_snow",
        "distance_m": 0.43,
    }
    first = client.post("/api/incidents/outbound-call", headers=headers, json=body)
    second = client.post("/api/incidents/outbound-call", headers=headers, json=body)

    assert first.status_code == 202
    assert first.json()["duplicate"] is False
    assert second.status_code == 202
    assert second.json()["duplicate"] is True
    assert len(calls) == 1
    assert "phone" not in first.text.lower()
    assert api.store.latest().status == "answered"


def test_outbound_call_analyzes_front_camera_before_livekit_dispatch(
    tmp_path: Path, monkeypatch
) -> None:
    client = setup_api(tmp_path)
    monkeypatch.setenv("BEACON_API_TOKEN", "test-secret")
    dispatched = []

    def fake_analyze(_: bytes) -> tuple[SceneAnalysis, str]:
        return (
            SceneAnalysis(
                people_count=1,
                scene_description=("One person is lying on a snowy surface in front of the robot."),
            ),
            "gpt-5.6-luna",
        )

    async def fake_place(incident):
        dispatched.append(incident)
        return CallPlacement(
            room_name=f"beacon-{incident.id.lower()}",
            participant_identity="responder-camera-test",
            participant_id="PA_camera_test",
        )

    monkeypatch.setattr(api, "analyze_scene", fake_analyze)
    monkeypatch.setattr(api, "place_incident_call", fake_place)
    jpeg = base64.b64encode(b"\xff\xd8front-camera-frame\xff\xd9").decode()
    response = client.post(
        "/api/incidents/outbound-call",
        headers={
            "Authorization": "Bearer test-secret",
            "Idempotency-Key": "episode-camera-001",
        },
        json={
            "simulation_id": "everest-camera-001",
            "distance_m": 0.55,
            "camera_name": "G1-FRONT-CAMERA",
            "image_data_url": f"data:image/jpeg;base64,{jpeg}",
        },
    )

    assert response.status_code == 202
    incident = response.json()["incident"]
    assert incident["analysis_status"] == "complete"
    assert incident["analysis_model"] == "gpt-5.6-luna"
    assert incident["evidence_url"].endswith(".jpg")
    assert incident["scene_description"].startswith("One person is lying")
    assert len(dispatched) == 1
    assert dispatched[0].scene_description == incident["scene_description"]


def test_outbound_call_keeps_base_brief_when_camera_analysis_fails(
    tmp_path: Path, monkeypatch
) -> None:
    client = setup_api(tmp_path)
    monkeypatch.setenv("BEACON_API_TOKEN", "test-secret")
    dispatched = []

    def unavailable_analysis(_: bytes):
        raise SceneAnalysisError("vision unavailable")

    async def fake_place(incident):
        dispatched.append(incident)
        return CallPlacement(
            room_name=f"beacon-{incident.id.lower()}",
            participant_identity="responder-camera-fallback",
            participant_id="PA_camera_fallback",
        )

    monkeypatch.setattr(api, "analyze_scene", unavailable_analysis)
    monkeypatch.setattr(api, "place_incident_call", fake_place)
    jpeg = base64.b64encode(b"\xff\xd8front-camera-frame\xff\xd9").decode()
    response = client.post(
        "/api/incidents/outbound-call",
        headers={
            "Authorization": "Bearer test-secret",
            "Idempotency-Key": "episode-camera-fallback-001",
        },
        json={
            "simulation_id": "everest-camera-fallback-001",
            "distance_m": 0.60,
            "image_data_url": f"data:image/jpeg;base64,{jpeg}",
        },
    )

    assert response.status_code == 202
    assert response.json()["incident"]["analysis_status"] == "failed"
    assert len(dispatched) == 1
    assert dispatched[0].scene_description is None
