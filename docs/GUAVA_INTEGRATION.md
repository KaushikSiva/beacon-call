# Guava integration

BeaconCall uses Guava as the voice-agent sponsor integration, not as a logo-only dependency.

## Runtime path

1. `agent.listen_phone(GUAVA_AGENT_NUMBER)` attaches the local Expert to the Guava inbound number.
2. `on_call_received` accepts the incoming call.
3. `on_call_start` reads `runtime/latest-incident.json` and starts `camera_sighting_brief`.
4. `call.set_task` gives the Guava Dialog System the verified observation and a short checklist.
5. Two `guava.Field` values collect an optional operator name and a constrained response.
6. `on_question` answers follow-up questions from the same live incident while repeating the presence-only limitation.
7. `on_task_complete` writes the selected disposition back to local state and closes the call.
8. `on_session_end` logs the termination reason.

The camera image is never placed in the Guava task. Only camera name, time, confidence, frame region, and the explicit limitation are spoken.

## Why it runs locally on Mac

Guava's hosted Dialog System handles audio, speech recognition, conversation, and speech synthesis. The Python Expert connects to Guava over a persistent outbound WebSocket, so inbound phone calls can reach a developer laptop behind NAT without a public web server or ngrok.

## Evidence for judges

- Keep the local Expert logs visible during the call.
- Show the UI changing from `AWAITING INBOUND CALL` to the selected response.
- Open the Guava Conversations dashboard after the call.
- Show `main.py` briefly: the sponsor API is small enough to understand in seconds.

## Official references

- Guava quickstart: https://goguava.ai/docs/quickstart
- Architecture and Expert model: https://goguava.ai/docs/architecture-overview
- Inbound structured task example: https://goguava.ai/docs/inbound-form-filling
- Agent entrypoints and callbacks: https://goguava.ai/docs/agent
- Typed task fields: https://goguava.ai/docs/field

These pages were checked on August 29, 2026 while building BeaconCall with Guava CLI 0.40.0.
