# Render deployment runbook

BeaconCall deploys as one Docker-based Render web service. The container runs
the FastAPI API and the LiveKit agent worker as supervised sibling processes.
This is intentional: Render permits a persistent disk to be attached to only
one service, while both BeaconCall processes need the same incident store.

## 1. Prepare external services

Have these values ready before creating the Blueprint:

- LiveKit Cloud project URL, API key, and API secret;
- LiveKit outbound SIP trunk ID connected to Twilio;
- expected recipient's E.164 destination number;
- OpenAI API key.

The destination and credentials remain server-side. Do not put them in Git,
MuJoCo, Isaac, request payloads, or command-line arguments.

## 2. Create the Render Blueprint

Use the one-click button in the README, or:

1. Open <https://dashboard.render.com/blueprints>.
2. Select **New Blueprint Instance**.
3. Connect `KaushikSiva/beacon-call` and select `main`.
4. Review the `beacon-call` web service and 1 GB persistent disk.
5. Enter every value marked `sync: false`.
6. Apply the Blueprint and wait for the health check to pass.

The Blueprint uses the paid `starter` plan because Render persistent disks are
not available for free web services. It runs exactly one instance because a
disk-backed Render service cannot scale horizontally.

The required secret prompts are:

```text
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
LIVEKIT_SIP_TRUNK_ID
BEACON_DESTINATION_NUMBER
OPENAI_API_KEY
```

Render generates `BEACON_API_TOKEN`. Reveal and copy it from the service's
Environment page after deployment. Treat it as a secret.

## 3. Verify without placing a call

Set the deployed URL locally and verify health:

```bash
export BEACON_API_URL=https://YOUR-SERVICE.onrender.com
curl -fsS "$BEACON_API_URL/api/health"
```

Expected response:

```json
{"status":"ok","service":"beacon-call","voice_worker":"ready"}
```

Check the Render logs. They should show the Uvicorn API listening and the
LiveKit worker registering. A missing or invalid LiveKit credential causes the
worker to exit after bounded retries; the supervisor then stops the API so the
deployment cannot appear healthy with voice unavailable.

The service root should load the camera console. Do not use the outbound-call
endpoint merely as a health check because a valid request intentionally dials.

## 4. Connect Everest G1

In the shell where MuJoCo or Isaac runs:

```bash
export BEACON_API_URL=https://YOUR-SERVICE.onrender.com
read -rsp 'Beacon API token: ' BEACON_API_TOKEN; export BEACON_API_TOKEN; echo
```

Run the simulator disarmed first. Only when the expected recipient is ready,
use the simulator's two-part `--arm-live-call` procedure. The destination
number never leaves Render/BeaconCall.

## 5. Commission one expected call

From a local BeaconCall checkout:

```bash
export BEACON_API_URL=https://YOUR-SERVICE.onrender.com
read -rsp 'Beacon API token: ' BEACON_API_TOKEN; export BEACON_API_TOKEN; echo
make call-test
```

The script requires the exact confirmation `ARM-LIVE-CALL`, generates a unique
idempotency key, and sends no destination number. Confirm in Render and LiveKit
logs that the incident was queued, the agent was dispatched before dialing,
the acknowledgment or timeout was recorded, and the room was deleted.

## 6. Updates and cleanup

- Commits to `main` automatically rebuild and deploy the Blueprint service.
- Render sends `SIGTERM`; the supervisor forwards it to Uvicorn and LiveKit so
  active jobs can drain before the 180-second shutdown deadline.
- Incident JSON, evidence, and PDFs persist at `/app/runtime` on the encrypted
  Render disk.
- Rotate any credential exposed in chat, logs, screenshots, or shell history.
- A Render API key is needed only for later API/CLI automation, not this
  Dashboard deployment.

References: [Render Blueprints](https://render.com/docs/infrastructure-as-code),
[persistent disks](https://render.com/docs/disks),
[Docker services](https://render.com/docs/docker), and
[LiveKit production startup](https://docs.livekit.io/agents/server/startup-modes/).
