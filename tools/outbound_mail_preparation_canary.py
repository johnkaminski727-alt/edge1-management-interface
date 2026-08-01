#!/usr/bin/env python3
"""Run a signed, preparation-only canary against the loopback mail gateway."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import outbound_mail_preparation_auth as auth


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret-file", type=pathlib.Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8104")
    parser.add_argument("--client-id", default="wwcx-website-admin")
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def read_secret(path: pathlib.Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise SystemExit("secret file must be a regular non-symlink file")
    secret = path.read_text(encoding="utf-8").strip()
    if not 32 <= len(secret) <= 256:
        raise SystemExit("secret must contain between 32 and 256 characters")
    return secret


def request_json(
    base_url: str,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body if method != "GET" else None,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        return exc.code, payload


def main() -> int:
    args = parse_args()
    if args.base_url != "http://127.0.0.1:8104":
        raise SystemExit("canary is restricted to the approved loopback URL")
    secret = read_secret(args.secret_file)

    unsigned_status, unsigned_payload = request_json(
        args.base_url,
        "GET",
        "/outbound-mail/api/v1/status",
        b"",
        {},
        args.timeout,
    )
    assert unsigned_status == 401, (unsigned_status, unsigned_payload)
    assert unsigned_payload["error"] == "authentication_failed"

    status_headers = auth.build_headers(
        secret,
        args.client_id,
        "GET",
        "/outbound-mail/api/v1/status",
        b"",
    )
    signed_status, status_payload = request_json(
        args.base_url,
        "GET",
        "/outbound-mail/api/v1/status",
        b"",
        status_headers,
        args.timeout,
    )
    assert signed_status == 200, (signed_status, status_payload)
    assert status_payload["preparation_api"]["enabled"] is True
    assert status_payload["preparation_api"]["runtime_secret_configured"] is True
    assert status_payload["external_delivery_enabled"] is False
    assert status_payload["policy_enabled"] is False
    assert status_payload["sender_selection"]["live_sender_count"] == 0
    assert not any(item["ready"] for item in status_payload["providers"])

    body = json.dumps(
        {
            "identity_hint": "john-wwcx",
            "to": "phase-b-preparation-canary@example.invalid",
            "subject": "Phase B preparation-only canary",
            "body": "This synthetic canary must be prepared but never sent.",
            "message_class": "business_correspondence",
            "mailing_address": "151 2 Street South, Invermay, SK",
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    prepare_headers = auth.build_headers(
        secret,
        args.client_id,
        "POST",
        "/outbound-mail/api/v1/prepare",
        body,
    )
    prepare_headers["Content-Type"] = "application/json"
    prepare_status, prepare_payload = request_json(
        args.base_url,
        "POST",
        "/outbound-mail/api/v1/prepare",
        body,
        prepare_headers,
        args.timeout,
    )
    assert prepare_status == 200, (prepare_status, prepare_payload)
    assert prepare_payload["preparation_api"]["delivery_status"] == "prepared_not_sent"
    assert prepare_payload["preparation_api"]["authenticated_client_id"] == args.client_id
    assert prepare_payload["request"]["from_address"] == "john@ww.cx"
    assert prepare_payload["sender_selection"]["live_enabled"] is False
    assert "action_token" not in prepare_payload

    replay_status, replay_payload = request_json(
        args.base_url,
        "POST",
        "/outbound-mail/api/v1/prepare",
        body,
        prepare_headers,
        args.timeout,
    )
    assert replay_status == 409, (replay_status, replay_payload)
    assert replay_payload["error"] == "replay_detected"

    send_status, send_payload = request_json(
        args.base_url,
        "POST",
        "/outbound-mail/send",
        body,
        {"Content-Type": "application/json"},
        args.timeout,
    )
    assert send_status == 403, (send_status, send_payload)
    assert send_payload["error"] == "delivery_disabled"

    print("Outbound mail preparation API canary passed")
    print("Authenticated status: accepted")
    print("Signed preparation: prepared_not_sent")
    print("Nonce replay: rejected")
    print("External delivery: rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
