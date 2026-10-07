#!/usr/bin/env python3
"""Private read-only browser gateway for Edge1 Phone Intelligence."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_WEB_ROOT = Path("/var/www")
DEFAULT_API_ORIGIN = "http://127.0.0.1:8097"
DEFAULT_ACTOR = "edge1-phone-directory-gateway"

PHONE_DETAIL_RE = re.compile(
    r"^/api/intelligence/phones/([1-9][0-9]*)$"
)

ALLOWED_API_PATHS = {
    "/api/contacts/summary":
        "/v1/contacts/summary",
    "/api/contacts/entities":
        "/v1/contacts/entities",
    "/api/contacts/maintenance-summary":
        "/v1/contacts/maintenance-summary",
    "/api/contacts/maintenance":
        "/v1/contacts/maintenance",
    "/api/contacts/search":
        "/v1/contacts/search",
    "/api/contacts/unassigned":
        "/v1/contacts/unassigned",
    "/api/contacts/sources":
        "/v1/contacts/sources",
    "/api/contacts/observations":
        "/v1/contacts/observations",
    "/api/contacts/relationships":
        "/v1/contacts/relationships",
    "/api/contacts/relationship-evidence":
        "/v1/contacts/relationship-evidence",
    "/api/contacts/correlations":
        "/v1/contacts/correlations",
    "/api/contacts/evidence":
        "/v1/contacts/evidence",
    "/api/intelligence/dashboard":
        "/v1/intelligence/dashboard",
    "/api/intelligence/phones":
        "/v1/intelligence/phones",
    "/api/intelligence/sources":
        "/v1/intelligence/sources",
}

ALLOWED_QUERY_KEYS = {
    "/api/contacts/summary": set(),
    "/api/contacts/entities": {
        "q",
        "entity_type",
        "limit",
        "offset",
    },
    "/api/contacts/maintenance-summary": set(),
    "/api/contacts/maintenance": {
        "kind",
        "status",
        "q",
        "limit",
        "offset",
    },
    "/api/contacts/search": {
        "q",
        "kind",
        "limit",
    },
    "/api/contacts/unassigned": {
        "q",
        "limit",
    },
    "/api/contacts/sources": {
        "q",
        "verification",
        "source_kind",
        "provenance_id",
        "limit",
        "offset",
    },
    "/api/contacts/observations": {
        "q",
        "classification",
        "verification",
        "contact_point_id",
        "limit",
        "offset",
    },
    "/api/contacts/relationships": {
        "entity_id",
        "contact_point_id",
        "relationship_type",
        "confidence",
        "lifecycle_status",
        "limit",
        "offset",
    },
    "/api/contacts/relationship-evidence": {
        "relationship_id",
        "limit",
        "offset",
    },
    "/api/contacts/correlations": {
        "review_status",
        "correlation_type",
        "confidence",
        "entity_id",
        "contact_point_id",
        "limit",
        "offset",
    },
    "/api/contacts/evidence": {
        "assertion_id",
        "contact_point_id",
        "entity_id",
        "limit",
    },
    "/api/intelligence/phones": {
        "q",
        "status",
        "npa",
        "limit",
        "offset",
    },
    "/api/intelligence/sources": {
        "limit",
        "offset",
    },
}

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class GatewayError(Exception):
    pass


def credential_path() -> Path:
    explicit = os.environ.get(
        "EDGE1_PHONE_GATEWAY_SECRET",
        "",
    ).strip()

    if explicit:
        return Path(explicit)

    credentials_directory = os.environ.get(
        "CREDENTIALS_DIRECTORY",
        "",
    ).strip()

    if not credentials_directory:
        raise GatewayError(
            "gateway credential directory unavailable"
        )

    return (
        Path(credentials_directory)
        / "operations_api_secret"
    )


def read_secret(path: Path) -> bytes:
    try:
        if path.is_symlink():
            raise GatewayError(
                "gateway credential cannot be a symlink"
            )

        value = path.read_bytes().strip()

    except OSError as exc:
        raise GatewayError(
            "gateway credential unavailable"
        ) from exc

    if len(value) < 32:
        raise GatewayError(
            "gateway credential invalid"
        )

    return value


def translate_api_path(
    request_target: str,
) -> str | None:
    parsed = urllib.parse.urlsplit(
        request_target
    )

    upstream_path = ALLOWED_API_PATHS.get(
        parsed.path
    )

    if upstream_path is None:
        match = PHONE_DETAIL_RE.fullmatch(
            parsed.path
        )

        if match:
            if parsed.query:
                return None

            return (
                "/v1/intelligence/phones/"
                + match.group(1)
            )

        return None

    query = urllib.parse.parse_qs(
        parsed.query,
        keep_blank_values=True,
        strict_parsing=False,
    )

    allowed = ALLOWED_QUERY_KEYS.get(
        parsed.path,
        set(),
    )

    if any(key not in allowed for key in query):
        return None

    if parsed.path == "/api/intelligence/dashboard":
        if query:
            return None
        return upstream_path

    pairs: list[tuple[str, str]] = []

    for key in sorted(query):
        values = query[key]

        if len(values) != 1:
            return None

        pairs.append(
            (key, values[0])
        )

    if pairs:
        return (
            upstream_path
            + "?"
            + urllib.parse.urlencode(pairs)
        )

    return upstream_path


def signed_get(
    upstream_path: str,
    *,
    secret: bytes,
    actor: str = DEFAULT_ACTOR,
    api_origin: str = DEFAULT_API_ORIGIN,
    timeout: float = 5.0,
) -> tuple[int, bytes]:
    if api_origin != DEFAULT_API_ORIGIN:
        raise GatewayError(
            "operations API origin must remain loopback"
        )

    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(24)
    body = b""
    body_hash = hashlib.sha256(body).hexdigest()

    canonical = "\n".join(
        (
            "GET",
            upstream_path,
            timestamp,
            nonce,
            actor,
            body_hash,
        )
    ).encode("utf-8")

    signature = hmac.new(
        secret,
        canonical,
        hashlib.sha256,
    ).hexdigest()

    request = urllib.request.Request(
        api_origin + upstream_path,
        method="GET",
        headers={
            "Accept": "application/json",
            "X-WWCX-Actor": actor,
            "X-WWCX-Nonce": nonce,
            "X-WWCX-Timestamp": timestamp,
            "X-WWCX-Signature": signature,
        },
    )

    try:
        response = urllib.request.urlopen(
            request,
            timeout=timeout,
        )

        with response:
            status = int(response.status)
            payload = response.read(
                MAX_RESPONSE_BYTES + 1
            )

    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        payload = exc.read(
            MAX_RESPONSE_BYTES + 1
        )

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as exc:
        raise GatewayError(
            "operations API unavailable"
        ) from exc

    if len(payload) > MAX_RESPONSE_BYTES:
        raise GatewayError(
            "operations API response too large"
        )

    return status, payload


class PhoneIntelligenceGatewayHandler(
    SimpleHTTPRequestHandler
):
    server_version = "Edge1PhoneGateway/1"

    def __init__(
        self,
        *args: Any,
        directory: str | None = None,
        **kwargs: Any,
    ) -> None:
        root = directory or str(DEFAULT_WEB_ROOT)

        super().__init__(
            *args,
            directory=root,
            **kwargs,
        )

    def end_headers(self) -> None:
        self.send_header(
            "Cache-Control",
            "no-store",
        )
        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )
        self.send_header(
            "Referrer-Policy",
            "no-referrer",
        )
        self.send_header(
            "X-Frame-Options",
            "DENY",
        )
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(
            self.path
        )

        if parsed.path.startswith(
            "/api/intelligence"
        ) or parsed.path.startswith(
            "/api/contacts"
        ):
            self.handle_intelligence_get()
            return

        super().do_GET()

    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlsplit(
            self.path
        )

        if parsed.path.startswith(
            "/api/intelligence"
        ):
            self.send_json(
                HTTPStatus.METHOD_NOT_ALLOWED,
                {
                    "error": "method_not_allowed",
                },
            )
            return

        super().do_HEAD()

    def do_POST(self) -> None:
        self.reject_mutation()

    def do_PUT(self) -> None:
        self.reject_mutation()

    def do_PATCH(self) -> None:
        self.reject_mutation()

    def do_DELETE(self) -> None:
        self.reject_mutation()

    def reject_mutation(self) -> None:
        self.send_json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {
                "error": "read_only_gateway",
            },
        )

    def handle_intelligence_get(self) -> None:
        upstream_path = translate_api_path(
            self.path
        )

        if upstream_path is None:
            self.send_json(
                HTTPStatus.NOT_FOUND,
                {
                    "error": "not_found",
                },
            )
            return

        try:
            secret = read_secret(
                credential_path()
            )

            status, payload = signed_get(
                upstream_path,
                secret=secret,
            )

        except GatewayError:
            self.send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "error":
                        "intelligence_backend_unavailable",
                },
            )
            return

        try:
            decoded = json.loads(
                payload.decode("utf-8")
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            self.send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "error":
                        "invalid_backend_response",
                },
            )
            return

        self.send_json(
            status,
            decoded,
        )

    def send_json(
        self,
        status: int,
        payload: Any,
    ) -> None:
        body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

        self.send_response(int(status))
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8098,
    )

    parser.add_argument(
        "--web-root",
        type=Path,
        default=DEFAULT_WEB_ROOT,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.host not in {
        "127.0.0.1",
        "::1",
    }:
        raise SystemExit(
            "Refusing non-loopback bind"
        )

    if not args.web_root.is_dir():
        raise SystemExit(
            "Web root does not exist"
        )

    handler = lambda *a, **kw: (
        PhoneIntelligenceGatewayHandler(
            *a,
            directory=str(args.web_root),
            **kw,
        )
    )

    server = ThreadingHTTPServer(
        (args.host, args.port),
        handler,
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
