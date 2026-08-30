import asyncio
from dataclasses import asdict

import pytest
from livekit import api

from beacon_call.livekit_service import place_incident_call
from beacon_call.models import Incident


def incident() -> Incident:
    return Incident(
        id="BC-1234ABCD",
        detected_at="2026-08-30T12:00:00Z",
        camera_name="G1-HEAD-CAM",
        confidence=1.0,
        frame_region="robot proximity envelope",
        summary="bounded simulation observation",
        status="queued",
        simulation_id="sim-1",
        observed_state="motionless_adult_in_snow",
        distance_m=0.12,
    )


def configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://livekit.test")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("LIVEKIT_SIP_TRUNK_ID", "trunk")
    monkeypatch.setenv("BEACON_DESTINATION_NUMBER", "+15550101234")


def test_dispatch_happens_before_dial_and_destination_is_not_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    events: list[str] = []

    class FakeDispatch:
        async def create_dispatch(self, request) -> None:
            assert request.agent_name == "beacon-incident-agent"
            events.append("dispatch")

    class FakeSip:
        async def create_sip_participant(self, request):
            assert request.sip_call_to == "+15550101234"
            assert request.wait_until_answered
            events.append("dial")
            return type("Participant", (), {"participant_id": "participant-1"})()

    class FakeRoom:
        async def delete_room(self, request) -> None:
            events.append(f"delete:{request.room}")

    class FakeLiveKitAPI:
        def __init__(self, **kwargs) -> None:
            assert kwargs["url"] == "wss://livekit.test"
            self.agent_dispatch = FakeDispatch()
            self.sip = FakeSip()
            self.room = FakeRoom()

        async def aclose(self) -> None:
            events.append("close")

    monkeypatch.setattr(api, "LiveKitAPI", FakeLiveKitAPI)
    placement = asyncio.run(place_incident_call(incident()))

    assert events == ["dispatch", "dial", "close"]
    assert placement.participant_id == "participant-1"
    assert "+15550101234" not in str(asdict(placement))


def test_failed_dial_deletes_dispatched_room(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    events: list[str] = []

    class FakeDispatch:
        async def create_dispatch(self, request) -> None:
            events.append("dispatch")

    class FakeSip:
        async def create_sip_participant(self, request):
            events.append("dial")
            raise RuntimeError("dial failed")

    class FakeRoom:
        async def delete_room(self, request) -> None:
            events.append("delete")

    class FakeLiveKitAPI:
        def __init__(self, **kwargs) -> None:
            self.agent_dispatch = FakeDispatch()
            self.sip = FakeSip()
            self.room = FakeRoom()

        async def aclose(self) -> None:
            events.append("close")

    monkeypatch.setattr(api, "LiveKitAPI", FakeLiveKitAPI)

    with pytest.raises(RuntimeError, match="dial failed"):
        asyncio.run(place_incident_call(incident()))
    assert events == ["dispatch", "dial", "delete", "close"]
