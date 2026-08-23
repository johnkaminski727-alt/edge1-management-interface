#!/usr/bin/env python3
"""Process Ava visual jobs from the existing signed WW.CX browser queue."""
from __future__ import annotations

import os
import signal
import sys
import time
from typing import Any

from ava_visual_generator import VisualError, process_visual
from private_ai_browser_worker import QUEUE_KEY_ID_ENV, QUEUE_SECRET_ENV, WorkerError, queue_call, required_env

WORKER_ID = os.environ.get("AVA_VISUAL_WORKER_ID", "edge1-ava-visual")
_STOP = False


def _stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def complete(request_id: str, outcome: str, queue_secret: str, queue_key_id: str, *, result: dict[str, Any] | None = None, error_code: str | None = None) -> None:
    payload: dict[str, Any] = {"action": "complete", "worker_id": WORKER_ID, "request_id": request_id, "outcome": outcome}
    if result is not None:
        payload["result"] = result
    if error_code is not None:
        payload["error_code"] = error_code
    response = queue_call(payload, queue_secret, queue_key_id)
    if response.get("status") != "accepted":
        raise WorkerError("queue did not accept visual completion")


def process_once(queue_secret: str, queue_key_id: str) -> float:
    claim = queue_call({"action": "claim_visual", "worker_id": WORKER_ID}, queue_secret, queue_key_id)
    if claim.get("status") == "idle":
        return max(1.0, min(10.0, float(claim.get("poll_after_ms", 2000)) / 1000.0))
    if claim.get("status") != "job":
        raise WorkerError("queue returned an unknown visual claim state")
    request_id = str(claim.get("request_id", ""))
    payload = claim.get("gateway_request")
    if not request_id or not isinstance(payload, dict) or str(payload.get("request_id", "")) != request_id:
        if request_id:
            complete(request_id, "failed", queue_secret, queue_key_id, error_code="visual_provider_error")
        return 2.0
    try:
        result = process_visual(payload, queue_secret, queue_key_id)
        complete(request_id, "completed", queue_secret, queue_key_id, result=result)
    except VisualError as exc:
        code = "visual_store_error" if "store" in str(exc).lower() else "visual_provider_error"
        complete(request_id, "failed", queue_secret, queue_key_id, error_code=code)
    return 0.1


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    queue_secret = required_env(QUEUE_SECRET_ENV)
    queue_key_id = required_env(QUEUE_KEY_ID_ENV)
    if len(queue_secret) < 32:
        raise WorkerError("configured queue signing secret is too short")
    if not os.environ.get("OPENAI_API_KEY", ""):
        raise WorkerError("OPENAI_API_KEY is not available")
    while not _STOP:
        try:
            delay = process_once(queue_secret, queue_key_id)
        except WorkerError as exc:
            print(f"ava-visual-worker: {exc}", file=sys.stderr)
            delay = 5.0
        if delay > 0:
            time.sleep(delay)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WorkerError as exc:
        print(f"ava-visual-worker: {exc}", file=sys.stderr)
        raise SystemExit(1)
