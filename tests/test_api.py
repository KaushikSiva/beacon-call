from pathlib import Path

from fastapi.testclient import TestClient

from beacon_call import api
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
