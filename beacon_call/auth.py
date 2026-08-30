"""Authentication for robot-originated incident requests."""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("BEACON_API_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="BEACON_API_TOKEN is not configured")
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")
