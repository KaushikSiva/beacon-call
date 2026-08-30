<div align="center">

<img src="assets/beaconcall-hero.png" alt="BeaconCall humanoid rescue robot detecting an upright hiker and preparing a voice briefing" width="100%" />

# BeaconCall

### A robot camera sees someone. Guava makes sure a human hears about it.

**BeaconCall turns a robot-camera person sighting into a live Guava voice briefing so an operator can respond quickly.**

[![macOS](https://img.shields.io/badge/macOS-camera--ready-111?style=flat-square&logo=apple)](#quickstart)
[![Guava](https://img.shields.io/badge/Guava-inbound_voice-62D84E?style=flat-square)](#guava-is-the-voice-layer)
[![Computer Vision](https://img.shields.io/badge/vision-COCO--SSD-111?style=flat-square)](#how-it-works)
[![Tests](https://img.shields.io/badge/tests-10_passing-62D84E?style=flat-square)](#verification)
[![Privacy](https://img.shields.io/badge/privacy-images_stay_local-111?style=flat-square)](#privacy-and-safety)

[60-second demo](#the-60-second-demo) · [Quickstart](#quickstart) · [Architecture](#architecture) · [Guava integration](docs/GUAVA_INTEGRATION.md) · [Hackathon deck](artifacts/BeaconCall-Guava-Demo.pdf)

</div>

---

## About

Camera alerts are easy to miss, especially when a robot is scouting away from its operator. BeaconCall confirms a person across three camera frames, prepares a concise observation, and gives that context to a Guava inbound voice agent. The responder calls the Guava number, hears what the robot saw, and records a clear next step through natural conversation.

The current project uses a Mac webcam as a stand-in for the robot camera. Later, the same observation endpoint can accept frames from a Unitree G1 without changing the Guava voice workflow.

> [!IMPORTANT]
> BeaconCall detects **presence only**. It does not identify people or claim that someone fell, is injured, is distressed, or needs emergency assistance.

## What happens

| 01 — See | 02 — Verify | 03 — Speak | 04 — Respond |
|---|---|---|---|
| The Mac camera detects a person locally. | Three consecutive detections create one incident. | Guava briefs an inbound caller on time, region, and confidence. | The caller chooses **acknowledged**, **monitor**, or **inspect**. |

<p align="center">
  <img src="assets/beaconcall-brief-ready.png" alt="BeaconCall interface showing a verified person sighting ready for a Guava inbound call" width="94%" />
</p>

## Why this matters

- **A camera alert is silent.** BeaconCall turns it into a conversation.
- **A single frame is noisy.** Temporal confirmation reduces one-frame false alarms.
- **AI should not invent emergencies.** Every briefing explicitly says that presence does not confirm distress.
- **Robots need human decisions.** Guava collects a bounded response and writes it back to the incident.
- **The prototype is demoable today.** No fall acting, fake injury, robot hardware, or public webhook is required.

## Guava is the voice layer

Guava is not a logo-only sponsor integration in BeaconCall. Its hosted Dialog System handles the live audio, speech recognition, conversational turn-taking, and synthesized voice, while the local Python **Expert** supplies the latest verified camera observation.

The Expert uses Guava's real inbound primitives:

- `listen_phone` attaches BeaconCall to a Guava number.
- `on_call_start` loads the latest camera sighting.
- `set_task` creates the briefing and response checklist.
- `Field` constrains the operator response to three choices.
- `on_question` answers follow-ups from live incident context.
- `on_task_complete` records the human decision in the local incident.

Guava Experts connect outward over a persistent WebSocket, so the inbound agent can run on a Mac behind NAT without exposing a local web server or using ngrok. See Guava's [architecture overview](https://goguava.ai/docs/architecture-overview), [inbound example](https://goguava.ai/docs/inbound-form-filling), and [Agent reference](https://goguava.ai/docs/agent).

### Why the operator calls inbound

BeaconCall intentionally uses Guava's supported inbound path rather than pretending to place an outbound call:

```text
person verified → voice brief ready → operator calls Guava → Beacon speaks → response recorded
```

The camera event prepares the call context and activates **Call for briefing**. The human initiates the inbound call.

## Architecture

```mermaid
flowchart LR
    A[Mac camera now<br/>G1 camera later] --> B[COCO-SSD<br/>person presence]
    B --> C{3 detections<br/>within 4 seconds?}
    C -- No --> B
    C -- Yes --> D[Local incident JSON<br/>+ evidence frame]
    D --> E[Guava Expert<br/>inbound listener]
    F[Responder calls<br/>Guava number] --> E
    E --> G[Spoken briefing<br/>+ structured response]
    G --> D
```

The system boundary is deliberate: the evidence image remains on the Mac. Guava receives only the camera name, timestamp, frame region, confidence, and presence-only limitation.

## Quickstart

### Requirements

- macOS with a camera
- Chrome recommended for WebGL inference
- Node.js 22+ and npm
- [uv](https://docs.astral.sh/uv/)
- [Guava CLI](https://goguava.ai/docs/quickstart)

### 1. Install

```bash
cd /Users/kaushiksivakumar/workspace/beacon-call
make setup
cp .env.example .env
```

### 2. Connect Guava

```bash
guava login
guava numbers list
```

Add the API key and purchased Guava number to `.env`:

```dotenv
GUAVA_API_KEY=gva-...
GUAVA_AGENT_NUMBER=+1...
```

### 3. Run

Terminal 1 — camera console:

```bash
make run
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080), click **Start Camera**, and allow camera permission.

Terminal 2 — Guava inbound Expert:

```bash
make agent-phone
```

No phone number yet? Exercise the same inbound Expert through Guava WebRTC:

```bash
make agent-webrtc
```

## The 60-second demo

1. Show an empty chair or doorway and the **Scanning / no person** state.
2. Walk into frame and stand normally for about two seconds.
3. Show the green bounding box, confidence, frame region, and **Brief ready** state.
4. Call the displayed Guava number and ask: **“What did the robot camera see?”**
5. Answer **“inspect camera feed”** when Beacon asks what to do.
6. Show the updated incident and the call in Guava Conversations.

Full presenter copy: [docs/DEMO.md](docs/DEMO.md)

## Integrate a Unitree G1 later

The voice agent and incident model do not need to change. Replace the browser producer with a G1 camera process that posts the same observation contract:

```http
POST /api/observations
Content-Type: application/json

{
  "person_present": true,
  "confidence": 0.91,
  "camera_name": "G1-HEAD-CAM",
  "bbox": {
    "x": 220,
    "y": 80,
    "width": 180,
    "height": 410,
    "frame_width": 1280,
    "frame_height": 720
  }
}
```

Post three qualifying observations within four seconds. BeaconCall creates the same incident and Guava reads it on the next inbound call.

## Privacy and safety

- Camera inference runs locally in the browser.
- Evidence frames remain under the ignored `runtime/` directory.
- No facial recognition or identity matching is performed.
- No medical or distress classification is performed.
- The call repeats that a sighting is not a confirmed emergency.
- `.env` and runtime evidence are excluded from git.

## Verification

```bash
make test
```

Verified on Apple silicon:

- 8 Python tests
- 2 TypeScript tests
- Ruff clean
- TypeScript strict-mode clean
- Production Vite bundle succeeds
- npm production audit reports zero vulnerabilities
- Five-page deck artifacts validated

## Project map

```text
beacon-call/
├── beacon_call/          # API, incident store, and detection gate
├── web/                  # Camera-first operator console
├── main.py               # Guava inbound Expert
├── tests/                # Python behavior tests
├── docs/                 # Demo and sponsor implementation notes
├── assets/               # README hero and product screenshots
└── artifacts/            # PowerPoint, PDF, and browser deck
```

## Road to 5,000 stars

If this direction is useful, **star the repository** and share the 60-second demo. Stars help prioritize the integrations people actually want:

- [x] Mac camera presence detection
- [x] Guava inbound voice briefing
- [x] Human response written back to the incident
- [ ] Unitree G1 head-camera adapter
- [ ] RTSP and recorded-video inputs
- [ ] Multi-camera incident queue
- [ ] On-device Apple Vision/Core ML backend
- [ ] Community rescue-robot scenario pack

The fastest way to help is to open an issue with your camera source, robot platform, or rescue workflow.

## Hackathon materials

- [Five-slide PowerPoint](artifacts/BeaconCall-Guava-Demo.pptx)
- [Five-page PDF](artifacts/BeaconCall-Guava-Demo.pdf)
- [Browser deck](artifacts/BeaconCall-Guava-Demo.html)
- [Demo script](docs/DEMO.md)
- [Exact Guava implementation](docs/GUAVA_INTEGRATION.md)

## Contributing

Small, demoable pull requests are welcome. Good first contributions include a new camera adapter, better detection debouncing, accessibility improvements, and tests for unusual frame sizes. Please keep the project's core safety rule: **presence is not distress**.

---

<div align="center">

### Camera sighting. Guava briefing. Human response.

If BeaconCall should become a real G1 integration, give it a ⭐ and tell us what to build next.

</div>

## GitHub About settings

Use these values in **Repository → Settings → General**:

**Description**

> Turn robot-camera person sightings into live Guava voice briefings for human operators. Mac-first, G1-ready, and presence-only by design.

**Topics**

`robotics` · `computer-vision` · `voice-ai` · `guava` · `humanoid-robot` · `unitree-g1` · `emergency-response` · `tensorflowjs` · `fastapi` · `macos` · `hackathon`

**Social preview**

Upload [`assets/beaconcall-social-preview.png`](assets/beaconcall-social-preview.png) for the correctly cropped 2:1 GitHub preview.
