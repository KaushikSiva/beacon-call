"""Explicitly arm one outbound BeaconCall test incident."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from uuid import uuid4

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Place one explicitly armed simulation call")
    parser.add_argument("--arm-live-call", action="store_true", required=True)
    parser.add_argument("--distance-m", type=float, default=0.42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()
    if input("Type ARM-LIVE-CALL to place one real call: ").strip() != "ARM-LIVE-CALL":
        raise SystemExit("Call not armed")
    base_url = os.environ.get("BEACON_API_URL", "http://127.0.0.1:8080").rstrip("/")
    token = os.environ.get("BEACON_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("BEACON_API_TOKEN is not configured")
    episode_id = f"manual-{uuid4().hex[:12]}"
    request = urllib.request.Request(
        f"{base_url}/api/incidents/outbound-call",
        method="POST",
        data=json.dumps(
            {
                "simulation_id": episode_id,
                "observed_state": "motionless_adult_in_snow",
                "distance_m": args.distance_m,
                "camera_name": "MANUAL-CALL-TEST",
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Idempotency-Key": episode_id,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"BeaconCall rejected the incident: HTTP {exc.code}") from exc
    print(f"Queued incident {payload['incident']['id']}; watch the API and agent logs.")


if __name__ == "__main__":
    main()
