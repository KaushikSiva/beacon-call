import inspect
from pathlib import Path

import pytest

from beacon_call.models import SceneAnalysis
from beacon_call.store import IncidentStore
from beacon_call.voice import agent_instructions, incident_brief, is_acknowledgement
from main import incident_agent, parse_job_metadata, run_agent


def incident(tmp_path: Path):
    store = IncidentStore(tmp_path)
    created, _ = store.create_outbound(
        idempotency_key="voice-test-001",
        simulation_id="sim-voice-001",
        observed_state="motionless_adult_in_snow",
        distance_m=0.456,
        camera_name="G1-HEAD-CAM",
    )
    return created


def test_brief_is_deterministic_and_observation_bounded(tmp_path: Path) -> None:
    report = incident_brief(incident(tmp_path))
    assert "simulation alert, not a real-world emergency" in report
    assert "0.46 meters" in report
    assert "vital signs are unknown" in report


def test_agent_instructions_forbid_inference(tmp_path: Path) -> None:
    instructions = agent_instructions(incident(tmp_path))
    assert "Do not diagnose injury" in instructions
    assert "claim that emergency services were contacted" in instructions


def test_brief_includes_completed_front_camera_description(tmp_path: Path) -> None:
    store = IncidentStore(tmp_path)
    created, _ = store.create_outbound(
        idempotency_key="voice-camera-001",
        simulation_id="sim-voice-camera-001",
        observed_state="motionless_adult_in_snow",
        distance_m=0.62,
        camera_name="G1-FRONT-CAMERA",
        evidence_expected=True,
    )
    analyzed = store.record_scene_analysis(
        created.id,
        analysis=SceneAnalysis(
            people_count=1,
            scene_description="One person is lying on snow beside a rocky ridge.",
        ),
        model="gpt-5.6-luna",
    )

    report = incident_brief(analyzed)

    assert "front-camera frame reports" in report
    assert analyzed.scene_description in report
    assert "not a medical assessment" in report


@pytest.mark.parametrize("text", ["Acknowledged", "Copy that", "I received it", "Got it"])
def test_acknowledgement_detection(text: str) -> None:
    assert is_acknowledgement(text)


def test_job_metadata_validation() -> None:
    assert (
        parse_job_metadata('{"incident_id":"BC-123", "participant_identity":"responder-123"}')[
            "incident_id"
        ]
        == "BC-123"
    )
    with pytest.raises(ValueError):
        parse_job_metadata("{}")


def test_production_agent_entrypoint_is_spawn_picklable() -> None:
    assert incident_agent.__module__ == "main"
    assert incident_agent.__qualname__ == "incident_agent"
    source = inspect.getsource(run_agent)
    assert "num_idle_processes=0" in source
    assert 'multiprocessing_context="spawn"' in source
