#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

required = {
    "deploy/configure-electrum-watch-rpc.sh": [
        "set -euo pipefail",
        "rpchost 127.0.0.1",
        "ELECTRUM_RPC_PASSWORD",
        "chmod 0640 /etc/electrum-watch/rpc.env",
    ],
    "deploy/install-electrum-watch-service.sh": [
        "set -euo pipefail",
        "Missing watch-only wallet",
        "chmod 0600",
        "systemctl enable --now edge1-electrum-watch.service",
    ],
    "deploy/electrum-watch-service-smoke-test.sh": [
        "systemctl is-active --quiet",
        "Electrum JSON-RPC health check passed",
        "RPC host is not localhost",
        "non-loopback address",
    ],
    "deploy/systemd/edge1-electrum-watch.service": [
        "User=electrum-watch",
        "ConditionPathExists=/etc/electrum-watch/rpc.env",
        "ProtectSystem=strict",
        "ReadWritePaths=/var/lib/electrum-watch",
        "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
    ],
    "docs/handoff/electrum-watch-only-service-runbook.md": [
        "Never import a seed phrase",
        "Bind Electrum JSON-RPC only to `127.0.0.1`",
        "Do not permit business159 to call Electrum RPC directly",
        "Rollback",
    ],
}

for relative_path, markers in required.items():
    path = ROOT / relative_path
    if not path.is_file():
        raise SystemExit(f"Missing Electrum service asset: {relative_path}")
    text = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in text:
            raise SystemExit(f"Missing marker in {relative_path}: {marker}")

unit = (ROOT / "deploy/systemd/edge1-electrum-watch.service").read_text(encoding="utf-8")
for forbidden in ("0.0.0.0", "PrivateKey", "seed phrase here", "rpcpassword="):
    if forbidden in unit:
        raise SystemExit(f"Forbidden systemd content: {forbidden}")

print("Electrum watch-only service validation passed")
