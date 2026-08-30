import type { DetectedObject, ObjectDetection } from "@tensorflow-models/coco-ssd";
import "./style.css";
import type { AppState, DetectionResult, Incident } from "./contracts";
import { confidenceLabel, incidentTime, statusLabel } from "./format";

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing #${id}`);
  return found as T;
}

const video = element<HTMLVideoElement>("cameraVideo");
const canvas = element<HTMLCanvasElement>("detectionCanvas");
const cameraButton = element<HTMLButtonElement>("cameraButton");
const resetButton = element<HTMLButtonElement>("resetButton");
const stage = element<HTMLDivElement>("cameraStage");
const emptyView = element<HTMLDivElement>("emptyView");
const systemDot = element<HTMLSpanElement>("systemDot");
const systemStatus = element<HTMLSpanElement>("systemStatus");
const frameRate = element<HTMLSpanElement>("frameRate");
const visionLabel = element<HTMLElement>("visionLabel");
const confidenceText = element<HTMLSpanElement>("confidenceLabel");
const confirmationText = element<HTMLSpanElement>("confirmationText");
const incidentRail = element<HTMLElement>("incidentRail");
const incidentKicker = element<HTMLSpanElement>("incidentKicker");
const incidentTitle = element<HTMLHeadingElement>("incidentTitle");
const incidentSummary = element<HTMLParagraphElement>("incidentSummary");
const incidentConfidence = element<HTMLElement>("incidentConfidence");
const incidentRegion = element<HTMLElement>("incidentRegion");
const incidentId = element<HTMLElement>("incidentId");
const incidentSeenAt = element<HTMLElement>("incidentTime");
const callInstruction = element<HTMLParagraphElement>("callInstruction");
const callButton = element<HTMLAnchorElement>("callButton");
const phoneNumber = element<HTMLElement>("phoneNumber");

let model: ObjectDetection | null = null;
let stream: MediaStream | null = null;
let inferenceRunning = false;
let lastInference = 0;
let currentPhone: string | null = null;
let currentIncidentId: string | null = null;
const inferenceIntervalMs = 520;

function setFlow(step: "camera" | "vision" | "incident" | "guava"): void {
  const order = ["camera", "vision", "incident", "guava"];
  const active = order.indexOf(step);
  document.querySelectorAll<HTMLElement>(".flow-step").forEach((node) => {
    node.classList.toggle("is-active", order.indexOf(node.dataset.step ?? "") <= active);
  });
}

function resetIncidentUi(required = 3): void {
  currentIncidentId = null;
  incidentRail.classList.remove("has-incident");
  incidentKicker.textContent = "NO ACTIVE SIGHTING";
  incidentTitle.innerHTML = "Waiting for<br />a person.";
  incidentSummary.textContent =
    "Three consecutive camera confirmations will prepare a concise inbound briefing.";
  incidentConfidence.textContent = "—";
  incidentRegion.textContent = "—";
  incidentId.textContent = "—";
  incidentSeenAt.textContent = "—";
  confirmationText.textContent = `0 / ${required} CONFIRMATIONS`;
  callInstruction.textContent = "Start the Guava Expert, then dial after a sighting.";
  callButton.classList.add("is-disabled");
  callButton.removeAttribute("href");
  callButton.setAttribute("aria-disabled", "true");
  setFlow(stream ? "vision" : "camera");
}

function renderIncident(incident: Incident, required: number): void {
  currentIncidentId = incident.id;
  incidentRail.classList.add("has-incident");
  incidentKicker.textContent = statusLabel(incident.status);
  incidentTitle.innerHTML = "Person seen.<br />Brief ready.";
  incidentSummary.textContent = incident.summary;
  incidentConfidence.textContent = confidenceLabel(incident.confidence);
  incidentRegion.textContent = incident.frame_region.toUpperCase();
  incidentId.textContent = incident.id;
  incidentSeenAt.textContent = incidentTime(incident.detected_at);
  confirmationText.textContent = `${required} / ${required} VERIFIED`;
  callInstruction.textContent =
    incident.status === "awaiting_inbound_call"
      ? "Dial the Guava number. Beacon will speak this sighting and collect your response."
      : `Guava recorded: ${incident.response ?? incident.status}.`;
  if (currentPhone) {
    callButton.href = `tel:${currentPhone}`;
    callButton.classList.remove("is-disabled");
    callButton.setAttribute("aria-disabled", "false");
  }
  setFlow(incident.status === "awaiting_inbound_call" ? "incident" : "guava");
}

async function getState(): Promise<AppState> {
  const response = await fetch("/api/state", { cache: "no-store" });
  if (!response.ok) throw new Error(`State request failed: ${response.status}`);
  return (await response.json()) as AppState;
}

async function refreshState(): Promise<void> {
  try {
    const state = await getState();
    currentPhone = state.phone_number;
    phoneNumber.textContent = currentPhone ?? "SET GUAVA_AGENT_NUMBER";
    if (state.incident) renderIncident(state.incident, state.required_streak);
    else if (currentIncidentId) resetIncidentUi(state.required_streak);
  } catch (error) {
    console.warn(error);
  }
}

function drawPrediction(prediction: DetectedObject | null): void {
  const context = canvas.getContext("2d");
  if (!context || !video.videoWidth) return;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!prediction) return;
  const [x, y, width, height] = prediction.bbox;
  context.strokeStyle = "#62d84e";
  context.lineWidth = Math.max(3, canvas.width / 360);
  context.strokeRect(x, y, width, height);
  context.fillStyle = "#62d84e";
  context.font = `700 ${Math.max(16, canvas.width / 38)}px ui-monospace, monospace`;
  const label = `PERSON ${confidenceLabel(prediction.score)}`;
  const labelWidth = context.measureText(label).width + 22;
  context.fillRect(x, Math.max(0, y - 38), labelWidth, 38);
  context.fillStyle = "#071006";
  context.fillText(label, x + 11, Math.max(26, y - 11));
}

function captureEvidence(): string {
  const snapshot = document.createElement("canvas");
  const width = Math.min(960, video.videoWidth);
  const height = Math.round((width / video.videoWidth) * video.videoHeight);
  snapshot.width = width;
  snapshot.height = height;
  const context = snapshot.getContext("2d");
  if (context) {
    context.translate(width, 0);
    context.scale(-1, 1);
    context.drawImage(video, 0, 0, width, height);
  }
  return snapshot.toDataURL("image/jpeg", 0.78);
}

async function sendObservation(
  prediction: DetectedObject | null,
): Promise<DetectionResult> {
  const bbox = prediction
    ? {
        x: video.videoWidth - prediction.bbox[0] - prediction.bbox[2],
        y: prediction.bbox[1],
        width: prediction.bbox[2],
        height: prediction.bbox[3],
        frame_width: video.videoWidth,
        frame_height: video.videoHeight,
      }
    : null;
  const response = await fetch("/api/observations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      person_present: Boolean(prediction),
      confidence: prediction?.score ?? 0,
      camera_name: "MAC-01",
      bbox,
    }),
  });
  if (!response.ok) throw new Error(`Observation failed: ${response.status}`);
  return (await response.json()) as DetectionResult;
}

async function attachEvidence(incidentIdValue: string): Promise<void> {
  await fetch(`/api/incidents/${incidentIdValue}/evidence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_data_url: captureEvidence() }),
  });
}

async function detectFrame(timestamp: number): Promise<void> {
  requestAnimationFrame(detectFrame);
  if (!inferenceRunning || !model || video.readyState < 2) return;
  if (timestamp - lastInference < inferenceIntervalMs) return;
  lastInference = timestamp;

  const started = performance.now();
  try {
    const predictions = await model.detect(video, 10, 0.35);
    const person =
      predictions
        .filter((prediction) => prediction.class === "person")
        .sort((a, b) => b.score - a.score)[0] ?? null;
    drawPrediction(person);
    const result = await sendObservation(person);
    const latency = Math.round(performance.now() - started);
    frameRate.textContent = `${latency} MS`;
    confirmationText.textContent = `${result.streak} / ${result.required_streak} CONFIRMATIONS`;

    if (person) {
      stage.classList.add("has-person");
      visionLabel.textContent = result.created ? "PERSON VERIFIED" : "PERSON CANDIDATE";
      confidenceText.textContent = `CONFIDENCE ${confidenceLabel(person.score)}`;
      setFlow(result.created ? "incident" : "vision");
    } else {
      stage.classList.remove("has-person");
      visionLabel.textContent = "SCANNING / NO PERSON";
      confidenceText.textContent = "CONFIDENCE —";
    }

    if (result.incident) renderIncident(result.incident, result.required_streak);
    if (result.created && result.incident) {
      await attachEvidence(result.incident.id);
      incidentRail.animate(
        [
          { transform: "translateX(12px)", opacity: 0.5 },
          { transform: "translateX(0)", opacity: 1 },
        ],
        { duration: 420, easing: "cubic-bezier(.2,.8,.2,1)" },
      );
    }
  } catch (error) {
    console.error(error);
    visionLabel.textContent = "VISION RETRYING";
  }
}

async function startCamera(): Promise<void> {
  cameraButton.disabled = true;
  cameraButton.textContent = "LOADING VISION…";
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    const [tf, cocoSsd] = await Promise.all([
      import("@tensorflow/tfjs"),
      import("@tensorflow-models/coco-ssd"),
    ]);
    await tf.setBackend("webgl");
    await tf.ready();
    model = await cocoSsd.load({ base: "lite_mobilenet_v2" });
    inferenceRunning = true;
    stage.classList.remove("is-offline");
    emptyView.hidden = true;
    systemDot.classList.add("is-live");
    systemStatus.textContent = "CAMERA + VISION LIVE";
    cameraButton.textContent = "CAMERA LIVE";
    visionLabel.textContent = "SCANNING / NO PERSON";
    setFlow("vision");
  } catch (error) {
    console.error(error);
    cameraButton.disabled = false;
    cameraButton.textContent = "RETRY CAMERA";
    visionLabel.textContent = "CAMERA PERMISSION NEEDED";
  }
}

async function resetDemo(): Promise<void> {
  const response = await fetch("/api/demo/reset", { method: "POST" });
  const state = (await response.json()) as AppState;
  resetIncidentUi(state.required_streak);
  stage.classList.remove("has-person");
  visionLabel.textContent = stream ? "SCANNING / NO PERSON" : "WAITING FOR CAMERA";
  confidenceText.textContent = "CONFIDENCE —";
}

cameraButton.addEventListener("click", startCamera);
resetButton.addEventListener("click", resetDemo);
callButton.addEventListener("click", (event) => {
  if (callButton.classList.contains("is-disabled")) event.preventDefault();
  else setFlow("guava");
});

window.addEventListener("beforeunload", () => {
  stream?.getTracks().forEach((track) => track.stop());
});

resetIncidentUi();
void refreshState();
window.setInterval(refreshState, 1800);
requestAnimationFrame(detectFrame);
