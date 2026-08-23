#!/usr/bin/env python3
"""Pull authenticated WW.CX browser chat jobs and relay them to the loopback Private AI gateway.

Secrets are read only from environment variables. They are never accepted on the
command line or logged. The browser talks only to the WW.CX web queue; this worker
runs on Edge1 and is the only component that signs requests for 127.0.0.1:8787.

Ava Agent Controller v1 adds bounded planning, optional source routing, progress
telemetry, and result verification without granting scopes or host-write authority.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from ava_agent_controller import (
    AgentControllerError,
    build_plan,
    prepare_gateway_request,
    progress_payload,
    verify_gateway_result,
)

QUEUE_URL = os.environ.get("BB_BROWSER_QUEUE_URL", "https://ww.cx/api/bigbird-ai-worker.php")
GATEWAY_URL = os.environ.get("BB_BROWSER_GATEWAY_URL", "http://127.0.0.1:8787/v1/chat")
WORKER_ID = os.environ.get("BB_BROWSER_WORKER_ID", "edge1-private-ai-browser")
QUEUE_SECRET_ENV = "BB_BROWSER_WORKER_SECRET"
QUEUE_KEY_ID_ENV = "BB_BROWSER_WORKER_KEY_ID"
GATEWAY_SECRET_ENV = "BB_RELAY_SECRET"
GATEWAY_KEY_ID_ENV = "BB_RELAY_KEY_ID"
MAX_QUEUE_RESPONSE = 262_144
MAX_GATEWAY_RESPONSE = 1_048_576
DEFAULT_POLL_SECONDS = 2.0

_STOP = False


class WorkerError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: dict[str, str]
    body: bytes


def _stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise WorkerError(f"required environment variable is not set: {name}")
    return value


def compact_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def post(url: str, body: bytes, headers: dict[str, str], timeout: float, limit: int) -> HttpResult:
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise WorkerError("HTTP response exceeded the configured size limit")
            return HttpResult(int(response.status), {k.lower(): v for k, v in response.headers.items()}, raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read(limit + 1)
        if len(raw) > limit:
            raise WorkerError("HTTP error response exceeded the configured size limit") from exc
        return HttpResult(int(exc.code), {k.lower(): v for k, v in exc.headers.items()}, raw)
    except urllib.error.URLError as exc:
        raise WorkerError(f"HTTP transport unavailable: {type(exc.reason).__name__}") from exc


def queue_headers(body: bytes, secret: str, key_id: str, url: str) -> tuple[dict[str, str], str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "ww.cx" or parsed.port is not None:
        raise WorkerError("browser queue URL must remain exactly on https://ww.cx")
    path = parsed.path or "/"
    if path != "/api/bigbird-ai-worker.php" or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise WorkerError("browser queue URL path is not approved")
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    digest = sha256(body)
    canonical = f"POST\n{path}\n{timestamp}\n{nonce}\n{digest}"
    signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return ({
        "Content-Type": "application/json",
        "X-BB-Worker-Key-ID": key_id,
        "X-BB-Timestamp": timestamp,
        "X-BB-Nonce": nonce,
        "X-BB-Body-SHA256": digest,
        "X-BB-Signature": signature,
        "User-Agent": "wwcx-private-ai-browser-worker/2",
    }, nonce)


def verify_queue_response(result: HttpResult, request_nonce: str, secret: str) -> dict[str, Any]:
    timestamp = result.headers.get("x-bb-response-timestamp", "")
    body_hash = result.headers.get("x-bb-response-body-sha256", "")
    signature = result.headers.get("x-bb-response-signature", "")
    if not timestamp or not body_hash or not signature:
        raise WorkerError(f"queue returned unsigned HTTP {result.status}")
    if not hmac.compare_digest(body_hash, sha256(result.body)):
        raise WorkerError("queue response body hash mismatch")
    canonical = f"{result.status}\n{timestamp}\n{request_nonce}\n{body_hash}"
    expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise WorkerError("queue response signature mismatch")
    try:
        payload = json.loads(result.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerError("queue returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise WorkerError("queue returned a non-object JSON response")
    if result.status != 200:
        raise WorkerError(f"queue returned HTTP {result.status}")
    return payload


def queue_call(action_payload: dict[str, Any], secret: str, key_id: str) -> dict[str, Any]:
    body = compact_json(action_payload)
    headers, nonce = queue_headers(body, secret, key_id, QUEUE_URL)
    return verify_queue_response(post(QUEUE_URL, body, headers, 20.0, MAX_QUEUE_RESPONSE), nonce, secret)


def publish_progress(request_id: str, progress: dict[str, Any], queue_secret: str, queue_key_id: str) -> bool:
    payload = {
        "action": "progress",
        "worker_id": WORKER_ID,
        "request_id": request_id,
        "progress": progress,
    }
    try:
        response = queue_call(payload, queue_secret, queue_key_id)
    except WorkerError:
        return False
    return response.get("status") == "accepted"


def gateway_headers(body: bytes, secret: str, key_id: str, url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != 8787 or parsed.path != "/v1/chat":
        raise WorkerError("Private AI gateway URL must remain http://127.0.0.1:8787/v1/chat")
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    digest = sha256(body)
    canonical = f"POST\n{parsed.path}\n{timestamp}\n{nonce}\n{digest}"
    signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-BB-Key-Id": key_id,
        "X-BB-Timestamp": timestamp,
        "X-BB-Nonce": nonce,
        "X-BB-Body-Sha256": digest,
        "X-BB-Signature": signature,
        "User-Agent": "wwcx-private-ai-browser-worker/2",
    }


def gateway_call(payload: dict[str, Any], secret: str, key_id: str) -> dict[str, Any]:
    body = compact_json(payload)
    result = post(GATEWAY_URL, body, gateway_headers(body, secret, key_id, GATEWAY_URL), 90.0, MAX_GATEWAY_RESPONSE)
    try:
        decoded = json.loads(result.body.decode("utf-8")) if result.body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerError(f"gateway returned unreadable HTTP {result.status}") from exc
    if not isinstance(decoded, dict):
        raise WorkerError("gateway returned a non-object JSON response")
    if result.status < 200 or result.status >= 300:
        detail = str(decoded.get("detail", "gateway rejected request"))[:160]
        raise WorkerError(f"gateway HTTP {result.status}: {detail}")
    return decoded


def complete(request_id: str, outcome: str, queue_secret: str, queue_key_id: str, *, result: dict[str, Any] | None = None, error_code: str | None = None) -> None:
    payload: dict[str, Any] = {"action": "complete", "worker_id": WORKER_ID, "request_id": request_id, "outcome": outcome}
    if result is not None:
        payload["result"] = result
    if error_code is not None:
        payload["error_code"] = error_code
    response = queue_call(payload, queue_secret, queue_key_id)
    if response.get("status") != "accepted":
        raise WorkerError("queue did not accept completion")


def process_once(queue_secret: str, queue_key_id: str, gateway_secret: str, gateway_key_id: str) -> float:
    claim = queue_call({"action": "claim", "worker_id": WORKER_ID}, queue_secret, queue_key_id)
    if claim.get("status") == "idle":
        return max(1.0, min(10.0, float(claim.get("poll_after_ms", 2000)) / 1000.0))
    if claim.get("status") != "job":
        raise WorkerError("queue returned an unknown claim state")
    request_id = str(claim.get("request_id", ""))
    gateway_request = claim.get("gateway_request")
    if not request_id or not isinstance(gateway_request, dict):
        raise WorkerError("claimed job is missing request data")
    if str(gateway_request.get("request_id", "")) != request_id:
        complete(request_id, "failed", queue_secret, queue_key_id, error_code="gateway_rejected")
        return DEFAULT_POLL_SECONDS

    try:
        plan = build_plan(gateway_request)
        prepared_request = prepare_gateway_request(gateway_request, plan)
        publish_progress(
            request_id,
            progress_payload(plan, "planning", "Ava has a bounded read-only plan for this request.", "understand"),
            queue_secret,
            queue_key_id,
        )
        publish_progress(
            request_id,
            progress_payload(plan, "gathering", "Gathering only the approved context needed for the answer."),
            queue_secret,
            queue_key_id,
        )
        started = time.monotonic()
        result = gateway_call(prepared_request, gateway_secret, gateway_key_id)
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        publish_progress(
            request_id,
            progress_payload(plan, "verifying", "Checking the answer, evidence, and read-only boundary.", "verify"),
            queue_secret,
            queue_key_id,
        )
        trace = verify_gateway_result(request_id, result, plan)
        trace["gateway_duration_ms"] = elapsed_ms
        result = dict(result)
        result["agent_trace"] = trace
        publish_progress(
            request_id,
            progress_payload(plan, "complete", "Ava finished and verified this response.", "verify"),
            queue_secret,
            queue_key_id,
        )
        complete(request_id, "completed", queue_secret, queue_key_id, result=result)
    except (WorkerError, AgentControllerError) as exc:
        message = str(exc)
        if isinstance(exc, AgentControllerError):
            code = "agent_controller_rejected"
        else:
            code = "gateway_unavailable" if "transport unavailable" in message.lower() else "gateway_rejected"
        complete(request_id, "failed", queue_secret, queue_key_id, error_code=code)
    return 0.1


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    queue_secret = required_env(QUEUE_SECRET_ENV)
    queue_key_id = required_env(QUEUE_KEY_ID_ENV)
    gateway_secret = required_env(GATEWAY_SECRET_ENV)
    gateway_key_id = required_env(GATEWAY_KEY_ID_ENV)
    if len(queue_secret) < 32 or len(gateway_secret) < 32:
        raise WorkerError("configured signing secret is too short")
    while not _STOP:
        try:
            delay = process_once(queue_secret, queue_key_id, gateway_secret, gateway_key_id)
        except WorkerError as exc:
            print(f"private-ai-browser-worker: {exc}", file=sys.stderr)
            delay = 5.0
        if delay > 0:
            time.sleep(delay)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WorkerError as exc:
        print(f"private-ai-browser-worker: {exc}", file=sys.stderr)
        raise SystemExit(1)
