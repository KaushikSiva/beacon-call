import base64
from pathlib import Path

from fastapi.testclient import TestClient

from beacon_call import api
from beacon_call.models import SceneAnalysis
from beacon_call.store import IncidentStore
from beacon_call.vision_gate import PresenceGate


def setup_api(tmp_path: Path) -> TestClient:
    api.store = IncidentStore(tmp_path)
    api.gate = PresenceGate(required_hits=3, threshold=0.66, cooldown_seconds=20)
    return TestClient(api.app)


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


def test_evidence_runs_openai_scene_analysis_and_creates_pdf(
    tmp_path: Path, monkeypatch
) -> None:
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
