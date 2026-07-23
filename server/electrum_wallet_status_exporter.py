#!/usr/bin/env python3
"""Export sanitized watch-only wallet status for the WW.CX admin dashboard.

The exporter calls the loopback-only Electrum watch API using its protected
bearer token, normalizes only approved operational fields, and atomically
writes a public status document. It never emits wallet addresses, descriptors,
xpubs, transaction details, credentials, or raw backend responses.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_ENV = Path("/etc/electrum-watch/api.env")
DEFAULT_BASE = "http://127.0.0.1:8094"
DEFAULT_OUTPUT = Path("/var/www/edge1-status/bitcoin-wallet.json")
MAX_RESPONSE = 1024 * 1024


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def api_get(base: str, token: str, path: str) -> Any:
    request = urllib.request.Request(
        base.rstrip("/") + path,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "WWCX-Electrum-Wallet-Exporter/1.1",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read(MAX_RESPONSE + 1)
    if len(body) > MAX_RESPONSE:
        raise RuntimeError("Electrum API response exceeded limit")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("Electrum API returned an invalid response")
    return payload.get("result")


def number(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return "0"
    if isinstance(value, (int, float)):
        return format(value, ".8f")
    if isinstance(value, str):
        try:
            return format(float(value), ".8f")
        except ValueError:
            return "0"
    return "0"


def normalize(info: Any, balance: Any, state: Any) -> dict[str, Any]:
    info_map = info if isinstance(info, dict) else {}
    bal_map = balance if isinstance(balance, dict) else {}
    state_map = state if isinstance(state, dict) else {}

    confirmed = bal_map.get("confirmed", bal_map.get("confirmed_balance", 0))
    unconfirmed = bal_map.get("unconfirmed", bal_map.get("unconfirmed_balance", 0))
    unmatured = bal_map.get("unmatured", bal_map.get("unmatured_balance", 0))

    connected = bool(info_map.get("connected", info_map.get("server")))
    loaded = state_map.get("loaded") is True
    synchronized = loaded and state_map.get("synchronized") is True

    return {
        "format": "wwcx-bitcoin-wallet-status-v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_unix": int(time.time()),
        "service": {
            "state": "online",
            "backend": "electrum",
            "connected": connected,
        },
        "wallet": {
            "type": "watch-only",
            "private_keys_enabled": False,
            "loaded": loaded,
            "synchronized": synchronized,
            "network": str(info_map.get("network", "mainnet")),
            "transaction_count": int(info_map.get("transactions", info_map.get("tx_count", 0)) or 0),
        },
        "balance": {
            "confirmed_btc": number(confirmed),
            "unconfirmed_btc": number(unconfirmed),
            "unmatured_btc": number(unmatured),
        },
        "warnings": [],
    }


def failure_document(code: str) -> dict[str, Any]:
    return {
        "format": "wwcx-bitcoin-wallet-status-v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_unix": int(time.time()),
        "service": {"state": "unavailable", "backend": "electrum", "connected": False},
        "wallet": {"type": "watch-only", "private_keys_enabled": False, "loaded": False, "synchronized": False},
        "balance": {},
        "warnings": [code],
    }


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-env", type=Path, default=API_ENV)
    parser.add_argument("--api-base", default=DEFAULT_BASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.api_base not in {"http://127.0.0.1:8094", "http://localhost:8094"}:
        raise SystemExit("Electrum API base must remain loopback-only")

    try:
        token = load_env(args.api_env).get("ELECTRUM_API_TOKEN", "")
        if len(token) < 32:
            raise RuntimeError("API token is unavailable")
        info = api_get(args.api_base, token, "/v1/wallet/info")
        balance = api_get(args.api_base, token, "/v1/wallet/balance")
        state = api_get(args.api_base, token, "/v1/wallet/state")
        document = normalize(info, balance, state)
        exit_code = 0
    except (OSError, ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError):
        document = failure_document("backend_unavailable")
        exit_code = 1

    atomic_write(args.output, document)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
