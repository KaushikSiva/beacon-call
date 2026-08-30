"""LiveKit dispatch and Twilio-backed outbound SIP orchestration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from beacon_call.models import Incident
from beacon_call.voice import incident_brief

AGENT_NAME = "beacon-incident-agent"


@dataclass(frozen=True)
class CallPlacement:
    room_name: str
    participant_identity: str
    participant_id: str | None


def required_livekit_environment() -> dict[str, str]:
    names = (
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "LIVEKIT_SIP_TRUNK_ID",
        "BEACON_DESTINATION_NUMBER",
    )
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required voice configuration: {', '.join(missing)}")
    return values


async def place_incident_call(incident: Incident) -> CallPlacement:
    """Dispatch the agent first, then dial the configured recipient into its room."""

    from livekit import api

    config = required_livekit_environment()
    room_name = f"beacon-{incident.id.lower()}"
    participant_identity = f"responder-{incident.id.lower()}"
    metadata = json.dumps(
        {
            "incident_id": incident.id,
            "participant_identity": participant_identity,
            "brief": incident_brief(incident),
        }
    )
    livekit_api = api.LiveKitAPI(
        url=config["LIVEKIT_URL"],
        api_key=config["LIVEKIT_API_KEY"],
        api_secret=config["LIVEKIT_API_SECRET"],
    )
    try:
        await livekit_api.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=metadata,
            )
        )
        try:
            participant = await livekit_api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=config["LIVEKIT_SIP_TRUNK_ID"],
                    sip_call_to=config["BEACON_DESTINATION_NUMBER"],
                    room_name=room_name,
                    participant_identity=participant_identity,
                    participant_name="Everest G1 responder",
                    wait_until_answered=True,
                )
            )
        except Exception:
            await livekit_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
            raise
        return CallPlacement(
            room_name=room_name,
            participant_identity=participant_identity,
            participant_id=getattr(participant, "participant_id", None),
        )
    finally:
        await livekit_api.aclose()
