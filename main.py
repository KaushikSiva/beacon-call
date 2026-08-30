"""BeaconCall's Guava inbound voice Expert.

The Mac camera app writes a presence-only observation to ``runtime``. A rescuer
then calls the Guava number; this Expert loads that observation, speaks a short
briefing, and records the caller's response. It never claims a fall or emergency.
"""

from __future__ import annotations

import argparse
import logging
import os

import guava
from dotenv import load_dotenv
from guava import logging_utils
from guava.events import BotSessionEnded

from beacon_call.store import IncidentStore

load_dotenv()
logger = logging.getLogger("beacon_call.guava")
store = IncidentStore.from_environment()

agent = guava.Agent(
    name="Beacon",
    organization="BeaconCall Rescue Lab",
    purpose=(
        "Brief inbound rescue operators on the latest verified person sighting "
        "from a robot camera, clearly state its limitations, and record a response."
    ),
)


def _incident_brief() -> tuple[str | None, str]:
    incident = store.latest()
    if incident is None:
        return None, (
            "There is no active camera sighting. Tell the caller the camera has not "
            "confirmed a person yet, and ask them to check the BeaconCall console."
        )
    return incident.id, (
        f"Camera {incident.camera_name} detected one person in the {incident.frame_region} "
        f"of frame at {incident.confidence_percent} percent confidence. The sighting was "
        f"created at {incident.detected_at_display}. This is presence detection only, not "
        "a confirmed fall, injury, or emergency."
    )


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    logger.info("Inbound call received: %s", call_info)
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    incident_id, brief = _incident_brief()
    logger.info("Call %s briefing incident %s", call.id, incident_id or "none")
    call.set_task(
        "camera_sighting_brief",
        objective=(
            "You are Beacon, the calm voice layer for a robot-camera console. "
            f"Open with this exact operational context: {brief} "
            "Keep the call under one minute unless the caller asks questions."
        ),
        checklist=[
            guava.Say(f"BeaconCall camera update. {brief}"),
            guava.Field(
                key="operator_name",
                field_type="text",
                question="Who is acknowledging this camera update?",
                required=False,
            ),
            guava.Field(
                key="response",
                field_type="multiple_choice",
                question=(
                    "Should I mark this as acknowledged, continue monitoring, or ask someone "
                    "to inspect the camera feed?"
                ),
                choices=["acknowledged", "continue monitoring", "inspect camera feed"],
            ),
            (
                "Read back the chosen response and remind the caller that presence alone does "
                "not confirm distress."
            ),
        ],
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    incident_id, brief = _incident_brief()
    logger.info("Question on call %s: %s", call.id, question)
    if incident_id is None:
        return brief
    return (
        f"The latest verified observation is: {brief} BeaconCall stores only the camera "
        "region, timestamp, confidence, and a local evidence frame; it does not identify "
        "the person or diagnose their condition."
    )


@agent.on_task_complete("camera_sighting_brief")
def on_brief_complete(call: guava.Call) -> None:
    operator_name = call.get_field("operator_name") or "unnamed operator"
    response = call.get_field("response") or "acknowledged"
    incident = store.latest()
    if incident is not None:
        store.record_call_outcome(
            incident.id,
            call_id=str(call.id),
            operator_name=str(operator_name),
            response=str(response),
        )
    logger.info("Call %s completed by %s: %s", call.id, operator_name, response)
    call.hangup("BeaconCall has recorded your response. Stay safe.")


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    logger.info("Session %s ended: %s", call.id, event.termination_reason)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BeaconCall Guava Expert")
    channel = parser.add_mutually_exclusive_group(required=True)
    channel.add_argument("--phone", action="store_true", help="Receive inbound phone calls")
    channel.add_argument("--webrtc", action="store_true", help="Receive inbound browser calls")
    channel.add_argument("--local", action="store_true", help="Test with Mac microphone/speakers")
    channel.add_argument("--chat", action="store_true", help="Test in terminal text chat")
    return parser.parse_args()


if __name__ == "__main__":
    logging_utils.configure_logging()
    args = parse_args()
    if args.phone:
        number = os.environ.get("GUAVA_AGENT_NUMBER")
        if not number:
            raise SystemExit("Set GUAVA_AGENT_NUMBER in .env before using --phone")
        agent.listen_phone(number)
    elif args.webrtc:
        agent.listen_webrtc()
    elif args.chat:
        agent.chat()
    else:
        agent.call_local()
