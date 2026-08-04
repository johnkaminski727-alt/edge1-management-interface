#!/usr/bin/env python3
"""Loopback outbound-mail gateway server with fail-closed suppression checks.

This entrypoint preserves the existing preparation API and admin routes while
routing only POST /outbound-mail/send through the hashed-recipient suppression
gate. The committed gateway configuration remains disabled, so adding this
entrypoint does not activate a provider, sender, delivery path, or message.
"""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import outbound_mail_gateway_server as base
import outbound_mail_suppression_gate as suppression_gate


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUPPRESSION_DATABASE = (
    REPO_ROOT / "var" / "outbound-mail" / "delivery-state.sqlite3"
)


def guarded_send(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    payload: dict[str, Any],
    *,
    confirmation: bool,
    audit_path: str | Path,
    suppression_database: str | Path,
) -> dict[str, Any]:
    return suppression_gate.guarded_identity_send(
        base.identity_gateway.send_message,
        config,
        policy,
        identities,
        payload,
        confirmation=confirmation,
        audit_path=audit_path,
        suppression_database=suppression_database,
    )


class SuppressedGatewayHandler(base.GatewayHandler):
    """Existing gateway handler with a guarded send route."""

    @property
    def suppression_database(self) -> Path:
        return self.server.suppression_database  # type: ignore[attr-defined]

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/outbound-mail/send":
            super().do_POST()
            return
        try:
            config, policy, identities, audit_path, _nonce_path = self.application.load()
            max_bytes = config["admin"]["max_body_bytes"] + 65536
            payload = self._read_json(max_bytes)
            confirmation = payload.pop("confirm_send", False) is True
            result = guarded_send(
                config,
                policy,
                identities,
                payload,
                confirmation=confirmation,
                audit_path=audit_path,
                suppression_database=self.suppression_database,
            )
            self._send_json(HTTPStatus.ACCEPTED, result)
        except Exception as exc:
            self._handle_error(exc)


class SuppressedGatewayServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        application: base.GatewayApplication,
        suppression_database: Path,
    ) -> None:
        super().__init__(address, SuppressedGatewayHandler)
        self.application = application
        self.suppression_database = suppression_database.resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=base.DEFAULT_CONFIG)
    parser.add_argument("--identities", type=Path, default=base.DEFAULT_IDENTITIES)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--suppression-database",
        type=Path,
        default=DEFAULT_SUPPRESSION_DATABASE,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    application = base.GatewayApplication(args.config, args.identities)
    config, policy, identities, _audit_path, _nonce_path = application.load()
    status = base.identity_gateway.status_payload(config, policy, identities)
    host = args.host or config["listen"]["host"]
    port = args.port or config["listen"]["port"]
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Refusing non-loopback bind; use an authenticated reverse proxy")
    print(
        json.dumps(
            {
                "event": "outbound_mail_gateway_suppressed_start",
                "host": host,
                "port": port,
                "suppression_database": str(args.suppression_database),
                "suppression_database_present": args.suppression_database.is_file(),
                "send_route_suppression_required": True,
                "external_delivery_enabled": status["external_delivery_enabled"],
                "automatic_sender_selection": status["sender_selection"][
                    "automatic_selection_enabled"
                ],
            },
            sort_keys=True,
        )
    )
    server = SuppressedGatewayServer(
        (host, port),
        application,
        args.suppression_database,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
