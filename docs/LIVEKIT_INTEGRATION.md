# LiveKit and Twilio integration

BeaconCall uses LiveKit Agents for transcription and speech, and LiveKit SIP to dial a stored Twilio Elastic SIP trunk. The API follows LiveKit's required outbound order: dispatch the named agent into a room first, then create the SIP participant.

## Provision once

1. Create a LiveKit Cloud project.
2. Configure a Twilio Elastic SIP trunk and associate its originating number.
3. Create a stored outbound trunk in LiveKit and record its `ST_...` identifier.
4. Copy `.env.example` to `.env` and enter the LiveKit project credentials, trunk ID, OpenAI key, random Beacon API token, and server-side destination.
5. Run `make agent-dev` and confirm `beacon-incident-agent` registers with LiveKit.

The Twilio authentication secret belongs in the LiveKit outbound-trunk configuration, not in this repository or the incident request.

## Call sequence

```text
Everest proximity latch
  -> POST authenticated incident with Idempotency-Key
  -> persist queued incident
  -> dispatch beacon-incident-agent
  -> create SIP participant with wait_until_answered
  -> agent waits for the named participant
  -> deterministic report
  -> transcript acknowledgment or 45-second timeout
  -> persist outcome and PDF
  -> delete LiveKit room to disconnect the call
```

## Commissioning

Normal tests mock LiveKit. To validate the real path, start the API and agent in separate terminals, keep the LiveKit and Twilio dashboards open, and run `make call-test`. The script requires `ARM-LIVE-CALL` and creates a new idempotency key.

Check the incident state at `GET /api/state`. Expected progression is `queued -> dialing -> answered -> acknowledged`. Busy, rejected, unavailable, or configuration failures end in `failed`; no acknowledgment ends in `timed_out`.

## Failure checks

- `503 BEACON_API_TOKEN is not configured`: configure the API token before accepting robot requests.
- Agent dispatch fails: confirm the worker is running in `dev` or deployed mode and its name is `beacon-incident-agent`.
- SIP creation fails: confirm the stored trunk ID, Twilio termination URI, authentication, geographic permissions, and E.164 recipient.
- Call answers but is silent: confirm `OPENAI_API_KEY`, then inspect agent-worker logs for STT/TTS errors.
- Call remains connected: room deletion is the hang-up mechanism; inspect the worker for exceptions after the closing phrase.

Official references:

- <https://docs.livekit.io/agents/server/agent-dispatch/>
- <https://docs.livekit.io/telephony/making-calls/outbound-calls/>
- <https://docs.livekit.io/agents/multimodality/audio/>
