from pathlib import Path

import pytest

from beacon_call.store import IncidentStore
from beacon_call.voice import agent_instructions, incident_brief, is_acknowledgement
from main import parse_job_metadata


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
