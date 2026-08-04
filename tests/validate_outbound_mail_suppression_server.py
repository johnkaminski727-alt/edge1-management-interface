#!/usr/bin/env python3
"""Validate suppression-aware outbound-mail server routing."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import threading
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import outbound_mail_delivery_events as delivery_events
import outbound_mail_gateway_suppressed_server as server_module
import outbound_mail_suppression_gate as suppression_gate


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def synthetic_event(event_id: str, recipient_sha256: str) -> dict:
    return {
        "contract": delivery_events.CONTRACT,
        "event_id": event_id,
        "event_type": "complaint",
        "occurred_at": "2026-08-04T02:30:00Z",
        "provider_profile": "smtp_submission",
        "provider_message_id_sha256": "a" * 64,
        "control_id": "WWCX-SUPPRESSION-SERVER-TEST-0001",
        "recipient_sha256": recipient_sha256,
        "source_evidence_sha256": "b" * 64,
        "source_authentication": "synthetic_test",
        "source_verified": True,
        "diagnostic_class": "spam_complaint",
        "retryable": False,
        "raw_recipient_stored": False,
        "raw_payload_stored": False,
        "message_content_stored": False,
    }


def request_json(url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    method = "GET"
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def run_server(database: pathlib.Path, fake_send) -> tuple[server_module.SuppressedGatewayServer, threading.Thread, str]:
    application = server_module.base.GatewayApplication(
        server_module.base.DEFAULT_CONFIG,
        server_module.base.DEFAULT_IDENTITIES,
    )
    server_module.base.identity_gateway.send_message = fake_send
    server = server_module.SuppressedGatewayServer(
        ("127.0.0.1", 0),
        application,
        database,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, f"http://{host}:{port}"


payload = {
    "to": ["test.recipient@example.com"],
    "subject": "Suppression-aware route validation",
    "body": "Synthetic message body for local handler validation only.",
    "message_class": "business_correspondence",
    "confirm_send": True,
}

original_send = server_module.base.identity_gateway.send_message
try:
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary)

        missing_calls = [0]
        def missing_fake(*args, **kwargs):
            missing_calls[0] += 1
            return {"status": "accepted"}

        missing_server, missing_thread, missing_url = run_server(
            root / "missing.sqlite3",
            missing_fake,
        )
        try:
            health_status, health = request_json(missing_url + "/outbound-mail/healthz")
            check(health_status == 200 and health["status"] == "ok", "existing health route changed")
            status, body = request_json(missing_url + "/outbound-mail/send", payload)
            check(status == 403, "missing suppression state did not return HTTP 403")
            check(body["error"] == "delivery_disabled", "missing state error contract changed")
            check("suppression state is unavailable" in body["message"], "missing state message changed")
            check(missing_calls[0] == 0, "send callable ran with missing suppression state")
        finally:
            missing_server.shutdown()
            missing_server.server_close()
            missing_thread.join(timeout=5)

        recipient_hash = suppression_gate.recipient_sha256("test.recipient@example.com")
        suppressed_database = root / "suppressed.sqlite3"
        delivery_events.apply_event(
            suppressed_database,
            synthetic_event("event-server-suppressed-0001", recipient_hash),
            allow_synthetic=True,
        )
        suppressed_calls = [0]
        def suppressed_fake(*args, **kwargs):
            suppressed_calls[0] += 1
            return {"status": "accepted"}

        suppressed_server, suppressed_thread, suppressed_url = run_server(
            suppressed_database,
            suppressed_fake,
        )
        try:
            status, body = request_json(suppressed_url + "/outbound-mail/send", payload)
            check(status == 403, "active suppression did not return HTTP 403")
            check(body["error"] == "delivery_disabled", "suppression error contract changed")
            check("recipient suppression is active" in body["message"], "suppression message changed")
            check("example.com" not in json.dumps(body), "suppression response exposed recipient")
            check(suppressed_calls[0] == 0, "send callable ran for suppressed recipient")
        finally:
            suppressed_server.shutdown()
            suppressed_server.server_close()
            suppressed_thread.join(timeout=5)

        allowed_database = root / "allowed.sqlite3"
        delivery_events.apply_event(
            allowed_database,
            {
                **synthetic_event("event-server-allowed-0001", "c" * 64),
                "event_type": "provider_accepted",
                "diagnostic_class": "none",
            },
            allow_synthetic=True,
        )
        allowed_calls = [0]
        def allowed_fake(config, policy, identities, request_payload, *, confirmation, audit_path):
            allowed_calls[0] += 1
            check(confirmation is True, "handler lost explicit send confirmation")
            check(request_payload["to"] == ["test.recipient@example.com"], "handler changed payload")
            return {
                "status": "accepted",
                "provider": "synthetic",
                "provider_message_id": "synthetic-message-id",
            }

        allowed_server, allowed_thread, allowed_url = run_server(
            allowed_database,
            allowed_fake,
        )
        try:
            status, body = request_json(allowed_url + "/outbound-mail/send", payload)
            check(status == 202, "allowed guarded send did not return HTTP 202")
            check(allowed_calls[0] == 1, "allowed send callable did not run exactly once")
            check(body["status"] == "accepted", "allowed provider result changed")
            check(body["suppression_preflight"] == {
                "checked": True,
                "recipient_count": 1,
                "suppressed_recipient_count": 0,
            }, "suppression preflight response mismatch")
            check("test.recipient@example.com" not in json.dumps(body), "allowed response exposed recipient")
        finally:
            allowed_server.shutdown()
            allowed_server.server_close()
            allowed_thread.join(timeout=5)
finally:
    server_module.base.identity_gateway.send_message = original_send

source = (SERVER_ROOT / "outbound_mail_gateway_suppressed_server.py").read_text(encoding="utf-8")
for required in (
    "POST /outbound-mail/send",
    "SuppressedGatewayHandler",
    "suppression_database",
    "guarded_send",
    "suppression_database_present",
    "send_route_suppression_required",
    "Refusing non-loopback bind",
):
    check(required in source, f"suppression-aware server missing {required}")
check("base.identity_gateway.send_message" in source, "server does not preserve identity-aware send path")
check("super().do_POST()" in source, "server does not preserve existing non-send POST routes")

print("Outbound mail suppression-aware server validation passed")
print("Existing health and preparation routes remain delegated to the base handler")
print("Missing state and active suppression return 403 before the send callable")
print("Allowed recipients pass through exactly once with minimized preflight metadata")
print("No provider credential, external listener, live activation, or message traffic is introduced")
