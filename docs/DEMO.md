# BeaconCall demo script

Target duration: 45–60 seconds. No fall simulation, distress acting, or prerecorded emergency is needed.

## Before judging

1. Run `make run` and open `http://127.0.0.1:8080` in Chrome.
2. Run `make agent-phone` in a second terminal.
3. Confirm the Guava number appears in the right rail.
4. Put the camera on an empty chair or doorway, then click **Reset demo**. Have a second person ready to enter the frame.
5. Keep the Guava Conversations page open in another tab as sponsor proof.

## Spoken demo

**0–8 seconds — establish the problem**

“A robot camera can see someone, but a visual alert is easy to miss. BeaconCall turns that sighting into a conversation.”

**8–20 seconds — real camera detection**

Click **Start Camera**, then have two people walk into the frame.

“The local detector only needs to see one person to trigger. OpenAI then checks the captured frame, counts everyone it can see, and describes the observable scene.”

Point to the green boxes, OpenAI people count, scene description, and PDF link.

**20–42 seconds — Guava handoff**

“Outbound calling is not part of this demo, so we use Guava's supported inbound flow. The sighting is now a live briefing.”

Call the displayed Guava number. Ask: “What did the robot camera see?” When prompted, answer: “Acknowledged.” Let Beacon finish: “Thanks, I'll get it reported to the rescue team.”

**42–55 seconds — close with proof and integration**

Download the PDF, point to the updated incident state, then show the Guava Conversations entry.

“Today this runs from my Mac camera. Later the Unitree G1 posts the same observation contract, while the Guava Expert stays unchanged.”

## If phone setup is delayed

Run `make agent-webrtc` and use the Guava-generated inbound browser link. This exercises the same Expert callbacks and structured task, but the phone-number version is the preferred judging demo.

## What not to claim

- Do not say the system autonomously places a call; the responder initiates this inbound call.
- Do not say a detected person is injured or in distress.
- Do not say camera images are sent to Guava. One frame goes to OpenAI; the local file and report stay under `runtime/`, while Guava receives the text briefing.
- Do not claim that the PDF was transmitted to a real rescue service; it is a local demo report.
