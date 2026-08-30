from pathlib import Path

from beacon_call.models import BoundingBox
from beacon_call.store import IncidentStore, frame_region


def box_at(x: float) -> BoundingBox:
    return BoundingBox(
        x=x,
        y=20,
        width=100,
        height=200,
        frame_width=600,
        frame_height=400,
    )


def test_frame_region() -> None:
    assert frame_region(box_at(10)) == "left side"
    assert frame_region(box_at(250)) == "center"
    assert frame_region(box_at(480)) == "right side"


def test_incident_round_trip(tmp_path: Path) -> None:
    store = IncidentStore(tmp_path)
    incident = store.create(camera_name="MAC-01", confidence=0.91, bbox=box_at(250))
    assert incident.status == "awaiting_inbound_call"
    assert store.latest() == incident

    updated = store.record_call_outcome(
        incident.id,
        call_id="call-123",
        operator_name="Alex",
        response="inspect camera feed",
    )
    assert updated.status == "inspect"
    assert updated.operator_name == "Alex"


def test_reset_keeps_evidence_directory_safe(tmp_path: Path) -> None:
    store = IncidentStore(tmp_path)
    store.create(camera_name="MAC-01", confidence=0.90, bbox=box_at(250))
    store.reset()
    assert store.latest() is None
