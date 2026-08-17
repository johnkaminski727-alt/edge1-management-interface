#!/usr/bin/env python3
"""Run bounded signed Private AI chat acceptance scenarios.

The harness intentionally reads the HMAC secret only from an environment variable.
It never accepts the secret on the command line and never prints the secret or the
resulting signature.  It is suitable for local Edge1 loopback acceptance when the
operator deliberately supplies the existing gateway environment.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8787/v1/chat"
DEFAULT_SECRET_ENV = "BB_RELAY_SECRET"
DEFAULT_KEY_ID_ENV = "BB_RELAY_KEY_ID"
DEFAULT_GROUP = "usenet.comp.lang.python"


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_request(method: str, path: str, timestamp: str, nonce: str, body_sha: str) -> str:
    return f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_sha}"


def sign_request(secret: str, canonical: str) -> str:
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def compact_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def scenario_payload(
    scenario: str,
    *,
    request_id: str,
    user_id: str,
    role: str,
    group: str,
) -> dict[str, Any]:
    scopes: list[str] = []
    include_communications = False
    communications_groups: list[str] = []
    message = "E2E default omission check. Reply briefly."

    if scenario == "missing-scope":
        include_communications = True
        communications_groups = [group]
        message = "Python"
    elif scenario == "authorized":
        scopes = ["communications:read"]
        include_communications = True
        communications_groups = [group]
        message = "Python"
    elif scenario != "default":
        raise ValueError(f"unsupported scenario: {scenario}")

    return {
        "request_id": request_id,
        "user": {
            "id": user_id,
            "role": role,
            "scopes": scopes,
        },
        "message": message,
        "include_edge1_status": False,
        "include_messaging_status": False,
        "include_library": False,
        "include_documentation": False,
        "library_collections": [],
        "include_communications": include_communications,
        "communications_groups": communications_groups,
        "include_telephony": False,
    }


def signing_headers(*, body: bytes, url: str, key_id: str, secret: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or "/"
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    digest = body_sha256(body)
    canonical = canonical_request("POST", path, timestamp, nonce, digest)
    signature = sign_request(secret, canonical)
    return {
        "Content-Type": "application/json",
        "X-BB-Key-Id": key_id,
        "X-BB-Timestamp": timestamp,
        "X-BB-Nonce": nonce,
        "X-BB-Body-Sha256": digest,
        "X-BB-Signature": signature,
    }


def decode_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {"_non_json_response_bytes": len(raw)}


def source_keysets(value: Any) -> list[list[str]]:
    if not isinstance(value, list):
        return []
    out: list[list[str]] = []
    for item in value[:10]:
        if isinstance(item, dict):
            out.append(sorted(str(key) for key in item.keys()))
        else:
            out.append([f"<{type(item).__name__}>"])
    return out


def response_summary(status: int, payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"http_status": status}
    if not isinstance(payload, dict):
        summary["response_type"] = type(payload).__name__
        return summary

    for key in ("request_id", "mode", "communications_warning"):
        if key in payload:
            summary[key] = payload[key]

    sources = payload.get("sources")
    communications_sources = payload.get("communications_sources")
    summary["sources_count"] = len(sources) if isinstance(sources, list) else 0
    summary["communications_sources_count"] = (
        len(communications_sources) if isinstance(communications_sources, list) else 0
    )
    summary["communications_source_keysets"] = source_keysets(communications_sources)

    if "detail" in payload:
        detail = payload["detail"]
        if isinstance(detail, str):
            summary["detail"] = detail[:300]
        else:
            summary["detail_type"] = type(detail).__name__
    return summary


def assert_scenario(scenario: str, status: int, payload: Any) -> None:
    if scenario == "missing-scope":
        if 200 <= status < 300:
            raise AssertionError("missing-scope scenario unexpectedly succeeded")
        if isinstance(payload, dict):
            comms = payload.get("communications_sources")
            if isinstance(comms, list) and comms:
                raise AssertionError("authorization failure leaked communications sources")
        return

    if not (200 <= status < 300):
        raise AssertionError(f"{scenario} scenario returned HTTP {status}")
    if not isinstance(payload, dict):
        raise AssertionError(f"{scenario} scenario did not return a JSON object")

    comms = payload.get("communications_sources")
    if scenario == "default":
        if isinstance(comms, list) and comms:
            raise AssertionError("default scenario returned communications sources without opt-in")
        return

    if scenario == "authorized":
        if not isinstance(comms, list) or not comms:
            raise AssertionError("authorized scenario returned no communications sources")
        keysets = source_keysets(comms)
        provenance_markers = {
            "source_name",
            "source_item_id",
            "ingested_at_utc",
            "thread_key",
            "upstream",
            "group",
            "article_id",
            "message_id",
        }
        if not any(provenance_markers.intersection(keys) for keys in map(set, keysets)):
            raise AssertionError("authorized communications sources exposed no recognized provenance keys")
        return

    raise AssertionError(f"unknown scenario: {scenario}")


def send(url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, Any]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), decode_json(response.read())
    except urllib.error.HTTPError as exc:
        return int(exc.code), decode_json(exc.read())


def env_required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"required environment variable is not set: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=("default", "missing-scope", "authorized"))
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--secret-env", default=DEFAULT_SECRET_ENV)
    parser.add_argument("--key-id-env", default=DEFAULT_KEY_ID_ENV)
    parser.add_argument("--key-id", help="Non-secret gateway key identifier; overrides --key-id-env")
    parser.add_argument("--user-id", default="edge1-e2e-acceptance")
    parser.add_argument("--role", default="operator")
    parser.add_argument("--group", default=DEFAULT_GROUP)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    secret = env_required(args.secret_env)
    key_id = args.key_id or env_required(args.key_id_env)
    request_id = f"e2e-{args.scenario}-{int(time.time())}-{secrets.token_hex(4)}"
    payload = scenario_payload(
        args.scenario,
        request_id=request_id,
        user_id=args.user_id,
        role=args.role,
        group=args.group,
    )
    body = compact_json_bytes(payload)
    headers = signing_headers(body=body, url=args.url, key_id=key_id, secret=secret)
    status, response = send(args.url, body, headers, args.timeout)

    # Do not print the signed headers, secret, raw article bodies, or model answer.
    summary = response_summary(status, response)
    summary["scenario"] = args.scenario
    print(json.dumps(summary, indent=2, sort_keys=True))
    assert_scenario(args.scenario, status, response)
    print(f"E2E_{args.scenario.upper().replace('-', '_')}=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError, ValueError) as exc:
        print(f"E2E_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
