export type BoundingBox = {
  x: number;
  y: number;
  width: number;
  height: number;
  frame_width: number;
  frame_height: number;
};

export type Incident = {
  id: string;
  detected_at: string;
  camera_name: string;
  confidence: number;
  frame_region: string;
  summary: string;
  status:
    | "briefing_ready"
    | "queued"
    | "dialing"
    | "answered"
    | "acknowledged"
    | "monitoring"
    | "inspect"
    | "failed"
    | "timed_out";
  detector_people_count: number;
  people_count: number | null;
  scene_description: string | null;
  analysis_status: "pending" | "complete" | "failed";
  analysis_model: string | null;
  evidence_url: string | null;
  report_url: string | null;
  operator_name: string | null;
  response: string | null;
  simulation_id: string | null;
  observed_state: string | null;
  distance_m: number | null;
  call_error: string | null;
};

export type AppState = {
  incident: Incident | null;
  streak: number;
  required_streak: number;
  phone_number: string | null;
  detector: string;
  limitation: string;
};

export type DetectionResult = {
  streak: number;
  required_streak: number;
  created: boolean;
  incident: Incident | null;
};

export type EvidenceResult = {
  incident: Incident;
  analysis_error: string | null;
};
