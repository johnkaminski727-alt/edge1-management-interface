#!/usr/bin/env python3
"""Build a privacy-limited WireGuard identity projection for Edge1 management UI.

The projection joins configured WireGuard peer names/addresses with VPN registration
state. Raw public/private keys are never emitted. This module is read-only and does
not alter WireGuard, DNS, firewall, or registration state.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from vpn_access_registration import RegistrationStore
except ModuleNotFoundError:
    from server.vpn_access_registration import RegistrationStore

DEFAULT_WG_CONFIG = Path(os.environ.get("EDGE1_WG_CONFIG", "/etc/wireguard/wg0.conf"))
DEFAULT_DB = Path(os.environ.get("EDGE1_OPS_DB", "/var/lib/edge1-operations-api/audit.sqlite3"))
DEFAULT_OUTPUT = Path("/var/www/edge1-status/wireguard-identity.json")
DEFAULT_OWNERSHIP = Path("/opt/edge1-management-interface/config/networking/legacy-wireguard-ownership.json")
EDGE1_DNS = "10.77.0.1"

_ALLOWED = re.compile(r"^AllowedIPs\s*=\s*(.+)$", re.I)
_COMMENT = re.compile(r"^#\s*(.+?)\s*$")


def parse_wireguard_peers(text: str) -> list[dict[str, Any]]:
    peers: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending_comment = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _COMMENT.match(line)
        if match:
            label = match.group(1)[:160]
            if current is not None and not current.get("name"):
                current["name"] = label
            else:
                pending_comment = label
            continue
        if line.lower() == "[peer]":
            if current is not None:
                peers.append(current)
            current = {"name": pending_comment, "assigned_addresses": []}
            pending_comment = ""
            continue
        if current is None:
            continue
        match = _ALLOWED.match(line)
        if match:
            current["assigned_addresses"] = [part.strip() for part in match.group(1).split(",") if part.strip()]
    if current is not None:
        peers.append(current)
    return peers


def _registration_by_address(store: RegistrationStore) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for device in store.list_devices():
        for address in device.get("assigned_addresses", []):
            result[address] = device
    return result


def build_projection_from_peers(peers: list[dict[str, Any]], store: RegistrationStore, owner_names: dict[str, str] | None = None) -> dict[str, Any]:
    owner_names = owner_names or {}
    registrations = _registration_by_address(store)
    devices: list[dict[str, Any]] = []
    for peer in peers:
        registration = next(
            (registrations[a] for a in peer["assigned_addresses"] if a in registrations),
            {},
        )
        devices.append(
            {
                "name": registration.get("display_name") or peer["name"] or "Unnamed WireGuard peer",
                "assigned_addresses": peer["assigned_addresses"],
                "owner_subject": registration.get("owner") or "",
                "owner_display_name": owner_names.get(registration.get("owner") or "", ""),
                "registration_id": registration.get("id"),
                "registration_status": registration.get("status", "unregistered"),
                "last_seen_at": registration.get("last_seen_at"),
                "dns": {
                    "server": EDGE1_DNS,
                    "mode": "edge1-exclusive-target",
                    "filtering_enabled": bool(registration.get("dns_filtering_enabled", True)),
                    "split_dns_preserved": True,
                },
                "security": {
                    "spamhaus_enabled": bool(registration.get("spamhaus_enabled", True)),
                    "detailed_logging_permitted": bool(registration.get("detailed_logging_permitted", False)),
                    "quarantined": registration.get("status") == "quarantined",
                },
                "access": {
                    "proxy_required": bool(registration.get("proxy_required", False)),
                    "cache_eligible": bool(registration.get("cache_eligible", False)),
                },
            }
        )
    return {
        "schema_version": 1,
        "contract": "wwcx.wireguard-identity.v1",
        "source_of_truth": "vpn_registration_plus_wireguard_config",
        "mutations_enabled": False,
        "edge1_dns": EDGE1_DNS,
        "split_dns_preserved": True,
        "devices": devices,
        "summary": {
            "peer_count": len(devices),
            "registered_count": sum(1 for d in devices if d["registration_id"]),
            "policy_accepted_count": sum(1 for d in devices if d["registration_status"] in {"registered", "exempt"}),
            "owned_count": sum(1 for d in devices if d["owner_subject"]),
            "named_count": sum(1 for d in devices if not d["name"].startswith("Unnamed ")),
            "dns_filtering_enabled_count": sum(1 for d in devices if d["dns"]["filtering_enabled"]),
        },
    }



def build_projection(wg_config: Path, store: RegistrationStore, owner_names: dict[str, str] | None = None) -> dict[str, Any]:
    return build_projection_from_peers(parse_wireguard_peers(wg_config.read_text(encoding="utf-8")), store, owner_names)

def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_owner_names(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    subject = str(data.get("owner_subject") or "").strip()
    display = str(data.get("owner_display_name") or "").strip()
    return {subject: display} if subject and display else {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wg-config", type=Path, default=DEFAULT_WG_CONFIG)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ownership-manifest", type=Path, default=DEFAULT_OWNERSHIP)
    parser.add_argument("--peers-json", type=Path)
    args = parser.parse_args()
    store = RegistrationStore(args.db, read_only=True)
    owners = load_owner_names(args.ownership_manifest)
    if args.peers_json:
        peer_doc = json.loads(args.peers_json.read_text(encoding="utf-8"))
        if peer_doc.get("contract") != "wwcx.wireguard-peer-inventory.v1" or peer_doc.get("contains_keys") is not False:
            raise ValueError("peer inventory contract invalid")
        payload = build_projection_from_peers(peer_doc.get("peers") or [], store, owners)
    else:
        payload = build_projection(args.wg_config, store, owners)
    write_atomic(args.output, payload)
    print(json.dumps({"ok": True, "output": str(args.output), **payload["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
