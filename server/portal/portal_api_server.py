#!/usr/bin/env python3

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from carrier_operational import (
    ENDPOINT_SCOPES,
    identity_from_config,
    operational_response,
)


BASE = Path(__file__).resolve().parents[2]
PORTAL = BASE / "data/registry/interconnect/portal"
POLICY = BASE / "config/portal/hmac-policy.json"
CREDS = BASE / "config/portal/client-credentials.json"
AUDIT_LOG = Path("/var/lib/wwcx-portal/portal_access_events.jsonl")

LEGACY_ROUTES = {
    "/portal/status": "public-summary.json",
    "/portal/carriers": "carrier-status.json",
    "/portal/health": "health-summary.json",
    "/portal/interconnects": "interconnect-status.json",
    "/portal/numbers": "numbering-status.json",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit_event(client, endpoint, response_code, carrier_id=None, scope=None, reason=None):
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client_id": client,
        "carrier_id": carrier_id,
        "endpoint": endpoint,
        "required_scope": scope,
        "response_code": response_code,
        "correlation_id": str(uuid.uuid4()),
    }
    if reason:
        event["reason"] = reason

    with AUDIT_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")


def authenticate_request(headers):
    """Authenticate a request and return its configured portal identity."""

    policy = load(POLICY)
    client = headers.get("X-Portal-Client")

    if not policy.get("enabled"):
        if not client:
            return None
        client_config = load(CREDS).get("clients", {}).get(client)
        if not client_config:
            return None
        return identity_from_config(client, client_config)

    timestamp = headers.get("X-Portal-Timestamp")
    signature = headers.get("X-Portal-Signature")
    if not client or not timestamp or not signature:
        return None
    if client not in policy.get("allowed_clients", []):
        return None

    try:
        request_time = int(timestamp)
    except (TypeError, ValueError):
        return None

    if abs(time.time() - request_time) > policy["timestamp_window_seconds"]:
        return None

    client_config = load(CREDS).get("clients", {}).get(client)
    if not client_config or not client_config.get("secret"):
        return None

    expected = hmac.new(
        client_config["secret"].encode(),
        (client + timestamp).encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None

    return identity_from_config(client, client_config)


def verify_request(headers):
    """Backward-compatible boolean authentication helper."""

    return authenticate_request(headers) is not None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        identity = authenticate_request(self.headers)
        client_id = self.headers.get("X-Portal-Client", "unknown")
        required_scope = ENDPOINT_SCOPES.get(self.path)

        if identity is None:
            audit_event(client_id, self.path, 403, scope=required_scope, reason="authentication_failed")
            self.send_error_json(403, "authentication failed")
            return

        if self.path in LEGACY_ROUTES:
            self.send_file_json(identity, LEGACY_ROUTES[self.path])
            return

        if self.path in ENDPOINT_SCOPES:
            try:
                payload = operational_response(PORTAL, self.path, identity)
            except PermissionError as error:
                audit_event(
                    identity.client_id,
                    self.path,
                    403,
                    carrier_id=identity.carrier_id,
                    scope=required_scope,
                    reason=str(error),
                )
                self.send_error_json(403, str(error))
                return
            except FileNotFoundError:
                audit_event(
                    identity.client_id,
                    self.path,
                    503,
                    carrier_id=identity.carrier_id,
                    scope=required_scope,
                    reason="operational_export_unavailable",
                )
                self.send_error_json(503, "operational export unavailable")
                return

            self.send_payload(identity, payload, required_scope)
            return

        audit_event(
            identity.client_id,
            self.path,
            404,
            carrier_id=identity.carrier_id,
            reason="endpoint_not_found",
        )
        self.send_error_json(404, "endpoint not found")

    def send_file_json(self, identity, filename):
        try:
            body = (PORTAL / filename).read_bytes()
        except FileNotFoundError:
            self.send_error_json(503, "portal export unavailable")
            return

        audit_event(identity.client_id, self.path, 200, carrier_id=identity.carrier_id)
        self.send_bytes(200, body)

    def send_payload(self, identity, payload, required_scope):
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        audit_event(
            identity.client_id,
            self.path,
            200,
            carrier_id=identity.carrier_id,
            scope=required_scope,
        )
        self.send_bytes(200, body)

    def send_error_json(self, status, message):
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_bytes(status, body)

    def send_bytes(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    HTTPServer(("127.0.0.1", 8097), Handler).serve_forever()


if __name__ == "__main__":
    main()
