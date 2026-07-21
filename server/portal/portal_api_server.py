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
from carrier_workflows import (
    CHANGE_SCOPE,
    TICKET_SCOPE,
    WorkflowIdentity,
    WorkflowValidationError,
    create_change_request,
    create_ticket,
)

BASE = Path(__file__).resolve().parents[2]
PORTAL = BASE / "data/registry/interconnect/portal"
POLICY = BASE / "config/portal/hmac-policy.json"
CREDS = BASE / "config/portal/client-credentials.json"
AUDIT_LOG = Path("/var/lib/wwcx-portal/portal_access_events.jsonl")
TICKET_LOG = Path("/var/lib/wwcx-portal/carrier_tickets.jsonl")
CHANGE_LOG = Path("/var/lib/wwcx-portal/carrier_change_requests.jsonl")
MAX_REQUEST_BODY = 16 * 1024

LEGACY_ROUTES = {
    "/portal/status": "public-summary.json",
    "/portal/carriers": "carrier-status.json",
    "/portal/health": "health-summary.json",
    "/portal/interconnects": "interconnect-status.json",
    "/portal/numbers": "numbering-status.json",
}

WORKFLOW_ROUTES = {
    "/portal/carrier/tickets": TICKET_SCOPE,
    "/portal/carrier/change-requests": CHANGE_SCOPE,
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit_event(
    client,
    endpoint,
    response_code,
    carrier_id=None,
    scope=None,
    reason=None,
    resource_id=None,
):
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
    if resource_id:
        event["resource_id"] = resource_id

    with AUDIT_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")


def authenticate_request(headers, body=b""):
    """Authenticate a request and return its configured portal identity.

    GET requests retain the Phase 13D signature payload of client + timestamp.
    Requests with a body additionally require X-Portal-Content-SHA256 and bind
    that digest into the signature payload.
    """

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

    signature_payload = client + timestamp
    if body:
        content_digest = hashlib.sha256(body).hexdigest()
        if headers.get("X-Portal-Content-SHA256") != content_digest:
            return None
        signature_payload += content_digest

    expected = hmac.new(
        client_config["secret"].encode(),
        signature_payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None

    return identity_from_config(client, client_config)


def verify_request(headers):
    """Backward-compatible boolean authentication helper for GET requests."""

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

    def do_POST(self):
        required_scope = WORKFLOW_ROUTES.get(self.path)
        client_id = self.headers.get("X-Portal-Client", "unknown")
        if required_scope is None:
            audit_event(client_id, self.path, 404, reason="endpoint_not_found")
            self.send_error_json(404, "endpoint not found")
            return

        body = self.read_request_body()
        if body is None:
            return

        identity = authenticate_request(self.headers, body)
        if identity is None:
            audit_event(client_id, self.path, 403, scope=required_scope, reason="authentication_failed")
            self.send_error_json(403, "authentication failed")
            return
        if not identity.carrier_id:
            audit_event(
                identity.client_id,
                self.path,
                403,
                scope=required_scope,
                reason="carrier identity is required",
            )
            self.send_error_json(403, "carrier identity is required")
            return
        if required_scope not in identity.scopes:
            audit_event(
                identity.client_id,
                self.path,
                403,
                carrier_id=identity.carrier_id,
                scope=required_scope,
                reason="scope denied",
            )
            self.send_error_json(403, "scope denied")
            return

        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise WorkflowValidationError("JSON body must be an object")
            workflow_identity = WorkflowIdentity(identity.client_id, identity.carrier_id)
            if self.path == "/portal/carrier/tickets":
                record = create_ticket(TICKET_LOG, workflow_identity, payload)
                resource_id = record["ticket_id"]
            else:
                record = create_change_request(CHANGE_LOG, workflow_identity, payload)
                resource_id = record["change_request_id"]
        except (UnicodeDecodeError, json.JSONDecodeError):
            audit_event(
                identity.client_id,
                self.path,
                400,
                carrier_id=identity.carrier_id,
                scope=required_scope,
                reason="invalid_json",
            )
            self.send_error_json(400, "invalid JSON body")
            return
        except WorkflowValidationError as error:
            audit_event(
                identity.client_id,
                self.path,
                400,
                carrier_id=identity.carrier_id,
                scope=required_scope,
                reason=str(error),
            )
            self.send_error_json(400, str(error))
            return

        audit_event(
            identity.client_id,
            self.path,
            201,
            carrier_id=identity.carrier_id,
            scope=required_scope,
            resource_id=resource_id,
        )
        self.send_json(201, record)

    def read_request_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error_json(400, "invalid content length")
            return None
        if length <= 0:
            self.send_error_json(400, "request body is required")
            return None
        if length > MAX_REQUEST_BODY:
            self.send_error_json(413, "request body too large")
            return None
        return self.rfile.read(length)

    def send_file_json(self, identity, filename):
        try:
            body = (PORTAL / filename).read_bytes()
        except FileNotFoundError:
            self.send_error_json(503, "portal export unavailable")
            return
        audit_event(identity.client_id, self.path, 200, carrier_id=identity.carrier_id)
        self.send_bytes(200, body)

    def send_payload(self, identity, payload, required_scope):
        audit_event(
            identity.client_id,
            self.path,
            200,
            carrier_id=identity.carrier_id,
            scope=required_scope,
        )
        self.send_json(200, payload)

    def send_error_json(self, status, message):
        self.send_json(status, {"error": message})

    def send_json(self, status, payload):
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
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
