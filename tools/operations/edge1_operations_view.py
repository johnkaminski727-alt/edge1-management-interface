#!/usr/bin/env python3
"""G3: strict read-only, freshness-aware summaries of existing Edge1 observations.

Only explicitly whitelisted fields leave this process. Never send raw routes,
IP addresses, WireGuard peer identities, alert payloads, or firewall rules.
No active probing, service commands, network writes, or execution.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path

MAX_BYTES = 512 * 1024
CORE_SERVICES = ("ufw", "wg-quick@wg0", "wireguard-nat", "crowdsec",
                 "crowdsec-firewall-bouncer", "AdGuardHome", "unbound",
                 "edge1-operations-api")
CORE_INTERFACES = ("ens3", "wg0")
SECURITY_COMPONENTS = ("ids", "dns", "spamhaus", "firewall",
                       "fail2ban", "proxy", "network_sensor")
STATES = {"healthy", "attention", "unavailable", "observed", "ready",
          "active_verified", "feed_ready", "not_observed", "limited",
          "partial", "stale", "not_deployed", "unknown", "unexpected"}
SERVICE_STATES = {"active", "inactive", "failed", "activating", "unknown"}
SOURCE_NAMES = ("core", "network_defense")


def _source(path: Path, *, core: bool, now: datetime) -> tuple[dict | None, dict]:
    result = {"available": False, "fresh": False, "generated_at": None,
              "age_seconds": None, "reason": "missing or invalid observation"}
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None, result
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None, result
        if core and (raw.get("schema_version") != "wwcx.core-observation.v1"
                     or raw.get("read_only") is not True
                     or raw.get("traffic_controls_changed") is not False):
            return None, result
        if not core and (raw.get("traffic_controls_changed") is not False
                         or not isinstance(raw.get("components"), dict)
                         or not isinstance(raw.get("sources"), dict)):
            return None, result
        stamp = raw.get("generated_at")
        if not isinstance(stamp, str):
            return None, result
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None, result
        age = int((now - parsed).total_seconds())
        result.update(available=True, fresh=-60 <= age <= 300,
                      generated_at=parsed.isoformat(), age_seconds=age,
                      reason="current" if -60 <= age <= 300 else "stale; cannot confirm live state")
        return raw, result
    except (OSError, TypeError, ValueError, KeyError, UnicodeError):
        return None, result


def _int_or_none(value):
    return value if type(value) is int and 0 <= value <= 1_000_000_000 else None


def summarize(core_path: Path, security_path: Path, *, now: datetime | None = None) -> dict:
    at = now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    core, core_status = _source(core_path, core=True, now=at)
    security, security_status = _source(security_path, core=False, now=at)
    result = {"schema": "edge1-operations-g3.v1", "read_only": True,
              "execution_allowed": False, "sources": {"core": core_status, "network_defense": security_status},
              "services": [], "interfaces": [], "routing": {"ipv4_forwarding": None, "ipv6_forwarding": None},
              "security": [], "summary": {"active_services": None, "observed_services": 0,
                                          "interface_up": None, "security_components_observed": None},
              "limitations": ["Service states do not prove end-to-end connectivity.",
                              "Firewall observations do not establish rollback safety.",
                              "No peer identifiers, raw routes, addresses, credentials or alert payloads are exposed."]}
    if core is not None:
        services = core.get("services") if isinstance(core.get("services"), dict) else {}
        for name in CORE_SERVICES:
            item = services.get(name)
            state = item.get("state") if isinstance(item, dict) else None
            if state not in SERVICE_STATES:
                state = "unknown"
            result["services"].append({"name": name,
                "state": state if core_status["fresh"] else "stale",
                "observed": state != "unknown" and core_status["fresh"]})
        result["summary"]["observed_services"] = sum(v["observed"] for v in result["services"])
        result["summary"]["active_services"] = sum(v["state"] == "active" for v in result["services"]) if core_status["fresh"] else None
        interfaces = core.get("interfaces") if isinstance(core.get("interfaces"), dict) else {}
        for name in CORE_INTERFACES:
            item = interfaces.get(name)
            valid = isinstance(item, dict) and type(item.get("available")) is bool and item.get("up") in (True, False, None)
            result["interfaces"].append({"name": name, "available": item["available"] if valid and core_status["fresh"] else None,
                                         "up": item["up"] if valid and core_status["fresh"] else None})
        result["summary"]["interface_up"] = sum(item["up"] is True for item in result["interfaces"]) if core_status["fresh"] else None
        routing = core.get("routing") if isinstance(core.get("routing"), dict) else {}
        if core_status["fresh"]:
            for key in ("ipv4_forwarding", "ipv6_forwarding"):
                v = routing.get(key)
                result["routing"][key] = v if type(v) is int and v in (0, 1) else None
    if security is not None:
        components = security.get("components") or {}
        for name in SECURITY_COMPONENTS:
            item = components.get(name)
            item = item if isinstance(item, dict) else {}
            state = item.get("state") if item.get("state") in STATES else "unknown"
            if not security_status["fresh"]:
                state = "stale"
            metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
            allow_metrics = {
                "spamhaus": ("combined_ipv4_networks", "ipv6_networks", "drop4_elements", "drop6_elements"),
                "ids": ("recent_alerts",), "dns": ("recent_events",),
                "network_sensor": ("normalized_events", "network_events"),
            }
            sanitized = {key: _int_or_none(metrics.get(key)) for key in allow_metrics.get(name, ())}
            result["security"].append({"name": name, "state": state,
                "observed": item.get("observed") is True and security_status["fresh"],
                "enforcement_verified": item.get("enforcement_verified") is True and security_status["fresh"],
                "metrics": sanitized})
        result["summary"]["security_components_observed"] = sum(item["observed"] for item in result["security"]) if security_status["fresh"] else None
    return result
