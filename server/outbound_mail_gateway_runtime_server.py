#!/usr/bin/env python3
"""Loopback outbound-mail gateway with strict runtime config/state roots.

This entrypoint combines the suppression-aware send route with root-owned
runtime configuration under `/etc/wwcx` and mutable state under
`/var/lib/wwcx-outbound-mail`. It does not enable any committed delivery gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import outbound_mail_gateway_server as base
import outbound_mail_gateway_suppressed_server as suppressed
import outbound_mail_runtime_application as runtime_application
import outbound_mail_runtime_paths as runtime_paths


DEFAULT_SUPPRESSION_DATABASE = (
    runtime_paths.DEFAULT_STATE_ROOT / "delivery-state.sqlite3"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=base.DEFAULT_CONFIG)
    parser.add_argument("--identities", type=Path, default=base.DEFAULT_IDENTITIES)
    parser.add_argument("--config-root", type=Path, default=runtime_paths.DEFAULT_CONFIG_ROOT)
    parser.add_argument("--state-root", type=Path, default=runtime_paths.DEFAULT_STATE_ROOT)
    parser.add_argument(
        "--suppression-database",
        type=Path,
        default=DEFAULT_SUPPRESSION_DATABASE,
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    application = runtime_application.RuntimeGatewayApplication(
        args.config,
        args.identities,
        config_root=args.config_root,
        state_root=args.state_root,
        require_root_owned_config=True,
    )
    config, policy, identities, _audit_path, _nonce_path = application.load()
    suppression_database = runtime_paths.resolve_state_path(
        args.suppression_database,
        repo_root=base.REPO_ROOT,
        state_root=args.state_root,
    )
    status = base.identity_gateway.status_payload(config, policy, identities)
    host = args.host or config["listen"]["host"]
    port = args.port or config["listen"]["port"]
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Refusing non-loopback bind; use an authenticated reverse proxy")

    print(
        json.dumps(
            {
                "event": "outbound_mail_gateway_runtime_start",
                "host": host,
                "port": port,
                "runtime_paths": application.resolved_path_summary(),
                "config_root": str(application.config_root),
                "state_root": str(application.state_root),
                "suppression_database": str(suppression_database),
                "suppression_database_present": suppression_database.is_file(),
                "send_route_suppression_required": True,
                "external_delivery_enabled": status["external_delivery_enabled"],
                "automatic_sender_selection": status["sender_selection"][
                    "automatic_selection_enabled"
                ],
            },
            sort_keys=True,
        )
    )
    server = suppressed.SuppressedGatewayServer(
        (host, port),
        application,
        suppression_database,
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
