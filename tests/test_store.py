from pathlib import Path

from beacon_call.models import BoundingBox, SceneAnalysis
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
    incident = store.create(
        camera_name="MAC-01",
        confidence=0.91,
        bbox=box_at(250),
        detector_people_count=1,
    )
    assert incident.status == "briefing_ready"
    assert store.latest() == incident

    analyzed = store.record_scene_analysis(
        incident.id,
        analysis=SceneAnalysis(
            people_count=2,
            scene_description="Two people are standing together in front of the camera.",
        ),
        model="gpt-5.6-luna",
    )
    assert analyzed.people_count == 2
    assert "2 people" in analyzed.summary
    report_path = tmp_path / "reports" / f"{incident.id}.pdf"
    assert report_path.read_bytes().startswith(b"%PDF")

    updated = store.record_call_outcome(
        incident.id,
        call_id="call-123",
        operator_name="Alex",
        response="inspect camera feed",
    )
    assert updated.status == "inspect"
    assert updated.operator_name == "Alex"
    assert updated.report_url == f"/api/reports/{incident.id}.pdf"


def test_reset_keeps_evidence_directory_safe(tmp_path: Path) -> None:
    store = IncidentStore(tmp_path)
    store.create(camera_name="MAC-01", confidence=0.90, bbox=box_at(250))
    store.reset()
    assert store.latest() is None


def test_outbound_incident_is_idempotent_across_store_instances(tmp_path: Path) -> None:
    store = IncidentStore(tmp_path)
    incident, duplicate = store.create_outbound(
        idempotency_key="episode-everest-0001",
        simulation_id="episode-0001",
        observed_state="motionless_adult_in_snow",
        distance_m=0.41,
        camera_name="G1-HEAD-CAM",
    )
    assert duplicate is False
    assert incident.status == "queued"

    reopened = IncidentStore(tmp_path)
    repeated, duplicate = reopened.create_outbound(
        idempotency_key="episode-everest-0001",
        simulation_id="different-value-is-ignored",
        observed_state="motionless_adult_in_snow",
        distance_m=0.12,
        camera_name="G1-HEAD-CAM",
    )
    assert duplicate is True
    assert repeated.id == incident.id
    assert repeated.distance_m == 0.41
