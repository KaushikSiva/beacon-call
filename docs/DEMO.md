# BeaconCall demonstration

1. Run `make run` and `make agent-dev` in separate terminals.
2. Show that the camera needs three consecutive person detections before preparing a briefing.
3. Show the observable OpenAI scene description and local PDF.
4. Run `make call-test`, type `ARM-LIVE-CALL`, and answer the configured phone.
5. Let the deterministic simulation report finish, say “Acknowledged,” and verify the incident becomes `acknowledged` before the call disconnects.

Do not claim injury detection, identity recognition, emergency-service dispatch, an untested physical robot run, or a zero sim-to-real gap.
