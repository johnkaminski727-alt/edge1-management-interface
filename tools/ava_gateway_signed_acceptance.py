#!/usr/bin/env python3
"""Live signed acceptance probe for the rebuilt Ava read-only gateway.

Reads the local gateway relay identity without printing it. This probe is valid
before a model provider credential is configured: the signed request must reach
the retrieval boundary, return model_not_configured, and preserve bounded
Library evidence. It also verifies unsigned and replayed requests fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8787/v1/chat"
PATH = "/v1/chat"
ENV = Path("/etc/bigbird-ai-gateway.env")


def die(message: str) -> "NoReturn":
    raise SystemExit(f"FAIL: {message}")


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = ENV.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        die(f"gateway environment unavailable: {type(exc).__name__}")
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    for key in ("BB_RELAY_KEY_ID", "BB_RELAY_SECRET"):
        if not values.get(key):
            die(f"{key} is not configured")
    if len(values["BB_RELAY_SECRET"]) < 32:
        die("relay secret is unexpectedly short")
    return values


def request(body: bytes, headers: dict[str, str]) -> tuple[int, dict]:
    req = urllib.request.Request(URL, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=75) as resp:
            raw = resp.read(1_048_577)
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read(1_048_577)
        status = int(exc.code)
    except urllib.error.URLError as exc:
        die(f"gateway transport unavailable: {type(exc.reason).__name__}")
    if len(raw) > 1_048_576:
        die("gateway response exceeded limit")
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        die(f"gateway returned unreadable HTTP {status}")
    if not isinstance(payload, dict):
        die("gateway returned non-object JSON")
    return status, payload


def signed_headers(body: bytes, key_id: str, secret: str, nonce: str) -> dict[str, str]:
    timestamp = str(int(time.time()))
    digest = hashlib.sha256(body).hexdigest()
    canonical = f"POST\n{PATH}\n{timestamp}\n{nonce}\n{digest}"
    signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-BB-Key-Id": key_id,
        "X-BB-Timestamp": timestamp,
        "X-BB-Nonce": nonce,
        "X-BB-Body-Sha256": digest,
        "X-BB-Signature": signature,
        "User-Agent": "edge1-ava-signed-acceptance/1",
    }



def mcp_accept(env: dict[str, str]) -> None:
    request_id = "mcp-acceptance-" + secrets.token_hex(8)
    payload = {
        "request_id": request_id,
        "user": {
            "id": "edge1-mcp-acceptance",
            "role": "internal_viewer",
            "scopes": ["chat:general", "edge1:status:read"],
        },
        "message": "Use the Edge1 MCP connector to report the current Edge1 health status in one short sentence.",
        "include_edge1_status": True,
        "include_messaging_status": False,
        "include_library": False,
        "include_documentation": False,
        "library_collections": [],
        "include_communications": False,
        "communications_groups": [],
        "include_contacts": False,
        "include_telephony": False,
        "include_web": False,
        "visual_request": {"mode": "none", "size": "1024x1024", "source_kind": "", "source_id": ""},
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = secrets.token_hex(16)
    headers = signed_headers(body, env["BB_RELAY_KEY_ID"], env["BB_RELAY_SECRET"], nonce)
    status, result = request(body, headers)
    if status != 200:
        die(f"MCP signed request returned HTTP {status}: {result.get('detail','unexpected_gateway_response')}")
    if result.get("mcp_connector") != "enabled":
        die("MCP connector was not enabled for edge1:status:read")
    used = result.get("mcp_tools_used")
    if not isinstance(used, list) or "edge1_mcp_read" not in used:
        die("model did not invoke edge1_mcp_read")
    if result.get("mcp_shell_hosts") not in ([], None):
        die("MCP shell unexpectedly enabled during read-only acceptance")
    answer = result.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        die("MCP-backed response returned no answer")
    print(f"signed MCP read: PASS ({len(used)} tool call(s), {len(answer.strip())} answer chars)")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp", action="store_true", help="also run the live Edge1 MCP tool-call acceptance")
    args = parser.parse_args()
    if os.geteuid() != 0:
        die("run with sudo/root so the protected gateway environment can be read")
    env = load_env()

    unsigned_body = b'{"request_id":"unsigned-acceptance"}'
    status, _ = request(unsigned_body, {"Content-Type": "application/json"})
    if status != 401:
        die(f"unsigned request returned HTTP {status}, expected 401")
    print("unsigned request: PASS (401)")

    request_id = "acceptance-" + secrets.token_hex(8)
    payload = {
        "request_id": request_id,
        "user": {
            "id": "edge1-live-acceptance",
            "role": "internal_viewer",
            "scopes": ["chat:general", "library:search", "library:document:read"],
        },
        "message": "VPN",
        "include_edge1_status": False,
        "include_messaging_status": False,
        "include_library": True,
        "include_documentation": False,
        "library_collections": ["operations"],
        "include_communications": False,
        "communications_groups": [],
        "include_contacts": False,
        "include_telephony": False,
        "visual_request": {"mode": "none", "size": "1024x1024", "source_kind": "", "source_id": ""},
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = secrets.token_hex(16)
    headers = signed_headers(body, env["BB_RELAY_KEY_ID"], env["BB_RELAY_SECRET"], nonce)

    status, result = request(body, headers)
    if result.get("mode") != "read-only":
        die("gateway mode is not read-only")
    sources = result.get("sources")
    if not isinstance(sources, list) or not sources:
        die("signed Library request returned no bounded evidence")

    if status == 200:
        answer = result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            die("model-backed response returned no answer text")
        print(
            f"signed Library + model response: PASS "
            f"({len(sources)} evidence item(s), {len(answer.strip())} answer chars)"
        )
    elif status == 503 and result.get("detail") == "model_not_configured":
        print(
            f"signed Library retrieval: PASS "
            f"({len(sources)} evidence item(s), model intentionally unconfigured)"
        )
    else:
        detail = result.get("detail")
        if not isinstance(detail, str):
            detail = "unexpected_gateway_response"
        die(f"signed model-backed request returned HTTP {status}: {detail}")

    replay_status, _ = request(body, headers)
    if replay_status != 401:
        die(f"replayed nonce returned HTTP {replay_status}, expected 401")
    print("nonce replay rejection: PASS (401)")

    if args.mcp:
        mcp_accept(env)

    print("AVA SIGNED GATEWAY ACCEPTANCE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
