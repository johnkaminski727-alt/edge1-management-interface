#!/usr/bin/env python3
"""Loopback integration validation for the authenticated preparation-only mail API."""

from __future__ import annotations

import copy
import http.client
import json
import os
import pathlib
import sys
import tempfile
import threading
import uuid


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
API_PATH = "/outbound-mail/api/v1/prepare"
CLIENT_ID = "wwcx-website-admin"
SECRET = "integration-preparation-secret-with-at-least-32-characters"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import outbound_mail_gateway as gateway
import outbound_mail_gateway_server as gateway_server
import outbound_mail_preparation_auth as preparation_auth


def request_json(
    port: int,
    path: str,
    body: bytes,
    headers: dict[str, str],
) -> tuple[int, dict]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(
            "POST",
            path,
            body=body,
            headers={"Content-Type": "application/json", **headers},
        )
        response = connection.getresponse()
        raw = response.read()
        return response.status, json.loads(raw.decode("utf-8"))
    finally:
        connection.close()


def remove_if_present(path: pathlib.Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def main() -> int:
    base_config = gateway.load_json(CONFIG_PATH)
    gateway.validate_gateway_config(base_config)
    assert base_config["preparation_api"]["enabled"] is False
    assert base_config["enabled"] is False
    assert base_config["external_delivery_authorized"] is False
    assert base_config["admin"]["send_endpoint_enabled"] is False

    unique = uuid.uuid4().hex
    audit_relative = f"var/outbound-mail/integration-audit-{unique}.jsonl"
    nonce_relative = f"var/outbound-mail/integration-nonces-{unique}.sqlite3"
    audit_path = ROOT / audit_relative
    nonce_path = ROOT / nonce_relative

    config = copy.deepcopy(base_config)
    config["paths"]["audit_jsonl"] = audit_relative
    config["preparation_api"]["enabled"] = True
    config["preparation_api"]["nonce_store"] = nonce_relative
    gateway.validate_gateway_config(config)

    payload = {
        "identity_hint": "john-wwcx",
        "to": ["records@example.com"],
        "subject": "Preparation API integration validation",
        "body": "This body must not be copied into the JSONL audit event.",
        "message_class": "business_correspondence",
        "signer_name": "John Kaminski",
        "signer_title": "Authorized Representative",
        "mailing_address": "151 2 Street South, Invermay, SK",
        "case_id": "TEST-PREP-API-001",
        "action_id": "TEST-PREP-ACTION-001",
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    timestamp = 1_800_000_000
    nonce = "integration_nonce_1234567890"
    headers = preparation_auth.build_headers(
        SECRET,
        CLIENT_ID,
        "POST",
        API_PATH,
        body,
        timestamp=timestamp,
        nonce=nonce,
    )

    old_secret = os.environ.get(config["preparation_api"]["secret_env"])
    os.environ[config["preparation_api"]["secret_env"]] = SECRET

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_config = pathlib.Path(temporary_directory) / "gateway.json"
            temporary_config.write_text(json.dumps(config), encoding="utf-8")
            application = gateway_server.GatewayApplication(temporary_config)
            server = gateway_server.GatewayServer(("127.0.0.1", 0), application)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = int(server.server_address[1])
            try:
                original_time = preparation_auth.time.time
                preparation_auth.time.time = lambda: float(timestamp)
                try:
                    status, response = request_json(port, API_PATH, body, headers)
                    assert status == 200, response
                    assert response["preparation_api"]["contract"] == (
                        "wwcx.outbound-mail-preparation-api.v1"
                    )
                    assert response["preparation_api"]["authenticated_client_id"] == CLIENT_ID
                    assert response["preparation_api"]["delivery_status"] == "prepared_not_sent"
                    assert response["sender_selection"]["address"] == "john@ww.cx"
                    assert response["sender_selection"]["live_enabled"] is False
                    assert response["request"]["from_address"] == "john@ww.cx"
                    assert response["audit_record"]["from_address"] == "john@ww.cx"
                    assert response["audit_record"]["live_delivery_authorized"] is False
                    assert response["headers"]["X-WWCX-Tracking"] == (
                        "disclosed-action-link; no-hidden-pixel"
                    )
                    assert "action_token" not in response
                    assert response["body"].count("[WWCX-CORRESPONDENCE-CONTROL]") == 1
                    assert "Email: john@ww.cx" in response["body"]

                    replay_status, replay = request_json(port, API_PATH, body, headers)
                    assert replay_status == 409, replay
                    assert replay["error"] == "replay_detected"

                    invalid_headers = dict(headers)
                    invalid_headers[preparation_auth.HEADER_NONCE] = (
                        "invalid_signature_nonce_1234"
                    )
                    invalid_headers[preparation_auth.HEADER_SIGNATURE] = "0" * 64
                    invalid_status, invalid = request_json(
                        port,
                        API_PATH,
                        body,
                        invalid_headers,
                    )
                    assert invalid_status == 401, invalid
                    assert invalid["error"] == "authentication_failed"
                    assert invalid["message"] == "Preparation API authentication failed."
                finally:
                    preparation_auth.time.time = original_time
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
        assert len(audit_lines) == 1
        audit = json.loads(audit_lines[0])
        serialized_audit = json.dumps(audit, sort_keys=True)
        assert audit["event"] == "outbound_message_prepared_api"
        assert audit["client_id"] == CLIENT_ID
        assert audit["delivery_status"] == "prepared_not_sent"
        assert audit["sender_address"] == "john@ww.cx"
        assert payload["body"] not in serialized_audit
        assert nonce not in serialized_audit
        assert headers[preparation_auth.HEADER_SIGNATURE] not in serialized_audit
        assert nonce_path.is_file()
    finally:
        if old_secret is None:
            os.environ.pop(config["preparation_api"]["secret_env"], None)
        else:
            os.environ[config["preparation_api"]["secret_env"]] = old_secret
        for path in (
            audit_path,
            nonce_path,
            nonce_path.with_name(nonce_path.name + "-journal"),
            nonce_path.with_name(nonce_path.name + "-shm"),
            nonce_path.with_name(nonce_path.name + "-wal"),
        ):
            remove_if_present(path)

    print("Authenticated outbound mail preparation API integration validation passed")
    print("HMAC, replay protection, audit redaction, and no-send state verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
