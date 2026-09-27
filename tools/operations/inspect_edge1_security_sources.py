#!/usr/bin/env python3
"""Read-only G3.1 Edge1 collector triage. Emits ONLY a fixed sanitized JSON schema.

Does not expose raw JSON, IP addresses, unit environment, paths, errors, or
collector detail text. Never executes a command or changes production state.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from edge1_operations_view import _source, SECURITY_COMPONENTS, SOURCE_KEYS, STATES

SOURCE_CHECKS = tuple(sorted({key for keys in SOURCE_KEYS.values() for key in keys}))


def inspect(core: Path, defense: Path, *, now: datetime | None = None) -> dict:
    at = now or datetime.now(timezone.utc)
    raw_core, core_state = _source(core, core=True, now=at)
    raw_defense, defense_state = _source(defense, core=False, now=at)
    record = {
        "schema": "edge1-security-triage-g3-1.v1",
        "read_only": True,
        "core": core_state,
        "network_defense": defense_state,
        "components": [],
        "source_checks": [],
        "conclusion": "snapshot-only diagnostics; service health and nftables enforcement need separate verification",
    }
    if raw_core is not None:
        services = raw_core.get("services") if isinstance(raw_core.get("services"), dict) else {}
        for name in ("crowdsec", "crowdsec-firewall-bouncer", "AdGuardHome", "unbound", "ufw"):
            value = services.get(name)
            state = value.get("state") if isinstance(value, dict) else None
            record.setdefault("core_service_states", []).append({
                "name": name, "state": state if state in ("active", "inactive", "failed", "activating") else "unknown",
                "current": core_state["fresh"],
            })
    if raw_defense is not None:
        components = raw_defense["components"]
        sources = raw_defense["sources"]
        for name in SECURITY_COMPONENTS:
            data = components.get(name)
            data = data if isinstance(data, dict) else {}
            state = data.get("state")
            record["components"].append({
                "name": name, "reported_state": state if state in STATES else "unknown",
                "reported_observed": data.get("observed") is True,
                "reported_enforcement": data.get("enforcement_verified") is True,
                "snapshot_fresh": defense_state["fresh"],
            })
        for name in SOURCE_CHECKS:
            data = sources.get(name)
            if not isinstance(data, dict):
                continue
            status = ("stale" if data.get("stale") is True else
                      "current" if data.get("available") is True and data.get("stale") is False else
                      "unavailable" if data.get("available") is False else "unverified")
            record["source_checks"].append({"name": name, "state": status})
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, default=Path("/var/www/edge1-status/core-status.json"))
    parser.add_argument("--defense", type=Path, default=Path("/var/www/edge1-status/network-defense/data/network-defense.json"))
    args = parser.parse_args()
    print(json.dumps(inspect(args.core, args.defense), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
