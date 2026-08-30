# BeaconCall demo script

Target duration: 45–60 seconds. No fall simulation, distress acting, or prerecorded emergency is needed.

## Before judging

1. Run `make run` and open `http://127.0.0.1:8080` in Chrome.
2. Run `make agent-phone` in a second terminal.
3. Confirm the Guava number appears in the right rail.
4. Put the camera on an empty chair or doorway, then click **Reset demo**.
5. Keep the Guava Conversations page open in another tab as sponsor proof.

## Spoken demo

**0–8 seconds — establish the problem**

“A robot camera can see someone, but a visual alert is easy to miss. BeaconCall turns that sighting into a conversation.”

**8–20 seconds — real camera detection**

Click **Start Camera**, then walk into the frame.

“The detector does not fake a fall or diagnose distress. It only confirms a person across three frames.”

Point to the green box and the confidence/region fields.

**20–42 seconds — Guava handoff**

“Outbound calling is not part of this demo, so we use Guava's supported inbound flow. The sighting is now a live briefing.”

Call the displayed Guava number. Ask: “What did the robot camera see?” When prompted, answer: “Inspect camera feed.”

**42–55 seconds — close with proof and integration**

Point to the updated incident state, then show the Guava Conversations entry.

“Today this runs from my Mac camera. Later the Unitree G1 posts the same observation contract, while the Guava Expert stays unchanged.”

## If phone setup is delayed

Run `make agent-webrtc` and use the Guava-generated inbound browser link. This exercises the same Expert callbacks and structured task, but the phone-number version is the preferred judging demo.

## What not to claim

- Do not say the system autonomously places a call; the responder initiates this inbound call.
- Do not say a detected person is injured or in distress.
- Do not say camera images are sent to Guava. The image and incident file stay local; Guava receives the text briefing.
