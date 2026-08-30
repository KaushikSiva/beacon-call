from pathlib import Path

from guava.commands import ReadScriptCommand, SendInstructionCommand, SetTaskCommand
from guava.testing.mocks import MockCall

import main as guava_expert
from beacon_call.models import SceneAnalysis
from beacon_call.store import IncidentStore


def analyzed_store(tmp_path: Path) -> IncidentStore:
    store = IncidentStore(tmp_path)
    incident = store.create(
        camera_name="MAC-01",
        confidence=0.93,
        bbox=None,
        detector_people_count=1,
    )
    store.record_scene_analysis(
        incident.id,
        analysis=SceneAnalysis(
            people_count=2,
            scene_description=(
                "Two people are visible near the camera in front of padded wall panels."
            ),
        ),
        model="gpt-5.6-luna",
    )
    return store


def test_call_reads_complete_openai_scene_before_questions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(guava_expert, "store", analyzed_store(tmp_path))
    call = MockCall()

    guava_expert.on_call_start(call)

    assert isinstance(call._command_queue[0], ReadScriptCommand)
    spoken = call._command_queue[0].script
    assert "2 people seen. Brief ready." in spoken
    assert "OpenAI vision counted 2 people." in spoken
    assert "Two people are visible near the camera" in spoken
    assert isinstance(call._command_queue[1], SetTaskCommand)


def test_acknowledgement_reads_exact_closing_then_hangs_up(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(guava_expert, "store", analyzed_store(tmp_path))
    call = MockCall()
    call.set_field("operator_name", "Alex")
    call.set_field("response", "acknowledged")

    guava_expert.on_brief_complete(call)

    assert isinstance(call._command_queue[-2], ReadScriptCommand)
    assert call._command_queue[-2].script == guava_expert.CALL_CLOSING
    assert isinstance(call._command_queue[-1], SendInstructionCommand)
