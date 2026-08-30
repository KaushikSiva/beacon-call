"""BeaconCall LiveKit worker for one bounded outbound incident call."""

from __future__ import annotations

import asyncio
import json
import logging

from dotenv import load_dotenv

from beacon_call.livekit_service import AGENT_NAME
from beacon_call.store import IncidentStore
from beacon_call.voice import (
    CALL_CLOSING,
    CALL_TIMEOUT,
    agent_instructions,
    incident_brief,
    is_acknowledgement,
)

load_dotenv()
logger = logging.getLogger("beacon_call.livekit_agent")
store = IncidentStore.from_environment()


def parse_job_metadata(raw: str) -> dict[str, str]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("LiveKit job metadata is not valid JSON") from exc
    if not isinstance(value, dict):
        raise TypeError("LiveKit job metadata must be an object")
    required = ("incident_id", "participant_identity")
    missing = [name for name in required if not str(value.get(name, "")).strip()]
    if missing:
        raise ValueError(f"LiveKit job metadata is missing: {', '.join(missing)}")
    return {str(key): str(item) for key, item in value.items()}


def run_agent() -> None:
    from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
    from livekit.plugins import openai

    server = AgentServer()

    @server.rtc_session(agent_name=AGENT_NAME)
    async def incident_agent(ctx: JobContext) -> None:
        metadata = parse_job_metadata(ctx.job.metadata)
        incident_id = metadata["incident_id"]
        incident = store.get(incident_id)
        if incident is None:
            raise RuntimeError(f"Unknown incident: {incident_id}")

        await ctx.connect()
        participant = await asyncio.wait_for(
            ctx.wait_for_participant(identity=metadata["participant_identity"]),
            timeout=90,
        )
        store.record_call_status(
            incident_id,
            status="answered",
            call_id=getattr(participant, "sid", None) or participant.identity,
        )

        session = AgentSession(
            stt=openai.STT(model="gpt-4o-mini-transcribe", language="en"),
            tts=openai.TTS(
                model="gpt-4o-mini-tts",
                voice="ash",
                instructions="Speak calmly, clearly, and professionally.",
            ),
            allow_interruptions=False,
        )
        acknowledged = asyncio.Event()

        @session.on("user_input_transcribed")
        def on_transcript(event) -> None:  # type: ignore[no-untyped-def]
            if not bool(getattr(event, "is_final", False)):
                return
            transcript = str(getattr(event, "transcript", "") or "").strip()
            if is_acknowledgement(transcript):
                acknowledged.set()
                return
            asyncio.create_task(
                session.say(
                    "The only confirmed facts are that this is a simulation, the person is "
                    "motionless in snow, and responsiveness and vital signs are unknown. "
                    "Please acknowledge receipt."
                )
            )

        await session.start(
            room=ctx.room,
            agent=Agent(instructions=agent_instructions(incident)),
        )
        await session.say(incident_brief(incident), allow_interruptions=False)
        try:
            await asyncio.wait_for(acknowledged.wait(), timeout=45)
        except TimeoutError:
            store.record_call_status(incident_id, status="timed_out")
            await session.say(CALL_TIMEOUT, allow_interruptions=False)
        else:
            store.record_call_outcome(
                incident_id,
                call_id=incident.call_id or participant.identity,
                operator_name="phone responder",
                response="acknowledged",
            )
            await session.say(CALL_CLOSING, allow_interruptions=False)
        finally:
            await ctx.delete_room()

    cli.run_app(server)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_agent()
