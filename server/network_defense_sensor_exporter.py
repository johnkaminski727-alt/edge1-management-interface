#!/usr/bin/env python3
"""Add the optional passive network sensor to the final Network Defense snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import network_defense_freshness_exporter as base


def load_correlation(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def augment_snapshot(snapshot: dict[str, Any], correlation: dict[str, Any]) -> dict[str, Any]:
    context = correlation.get("network_sensor_context")
    if not isinstance(context, dict):
        return snapshot
    summary = correlation.get("summary") if isinstance(correlation.get("summary"), dict) else {}
    categories = summary.get("category_counts") if isinstance(summary.get("category_counts"), dict) else {}
    event_count = safe_int(summary.get("network_sensor_event_count"))
    network_events = safe_int(categories.get("network"))
    observed = event_count > 0

    components = snapshot.setdefault("components", {})
    components["network_sensor"] = {
        "name": "Passive network sensor",
        "state": "observed" if observed else "ready",
        "observed": observed,
        "enforcement_verified": False,
        "detail": (
            "Full-link passive capture telemetry is feeding Security Correlation."
            if observed else
            "The passive sensor source is connected but no normalized events are present in the current correlation window."
        ),
        "metrics": {
            "normalized_events": event_count,
            "network_events": network_events,
            "profile": context.get("profile"),
            "mode": context.get("mode"),
            "restricted_payloads_copied": context.get("restricted_payloads_copied") is True,
        },
    }

    snapshot_summary = snapshot.setdefault("summary", {})
    snapshot_summary["component_count"] = len(components)
    snapshot_summary["observed_component_count"] = sum(1 for item in components.values() if item.get("observed"))
    snapshot_summary["verified_enforcement_count"] = sum(1 for item in components.values() if item.get("enforcement_verified"))

    correlation_context = snapshot.setdefault("correlation_context", {})
    correlation_context["network_sensor_event_count"] = event_count
    correlation_context["network_sensor_network_event_count"] = network_events

    limitations = snapshot.setdefault("limitations", [])
    statement = "Full PCAP and unrestricted recent sensor records remain in the root-restricted sensor archive; Network Defense receives normalized metadata only."
    if statement not in limitations:
        limitations.append(statement)
    return snapshot


def build_snapshot(
    network_path: Path = base.FINAL.BASE.BASE.BASE.DEFAULT_NETWORK,
    security_path: Path = base.FINAL.BASE.BASE.BASE.DEFAULT_SECURITY,
    correlation_path: Path = base.FINAL.BASE.BASE.BASE.DEFAULT_CORRELATION,
    operations_path: Path = base.FINAL.BASE.BASE.BASE.DEFAULT_OPERATIONS,
    spamhaus_path: Path = base.FINAL.BASE.BASE.BASE.DEFAULT_SPAMHAUS,
    spamhaus_live_state_path: Path = base.FINAL.BASE.BASE.BASE.DEFAULT_SPAMHAUS_LIVE_STATE,
    dns_policy_path: Path = base.FINAL.BASE.BASE.DEFAULT_DNS_POLICY,
    fail2ban_live_state_path: Path = base.FINAL.BASE.DEFAULT_FAIL2BAN_LIVE_STATE,
    nftables_live_state_path: Path = base.FINAL.DEFAULT_NFTABLES_LIVE_STATE,
    now=None,
) -> dict[str, Any]:
    snapshot = base.build_snapshot(
        network_path=network_path,
        security_path=security_path,
        correlation_path=correlation_path,
        operations_path=operations_path,
        spamhaus_path=spamhaus_path,
        spamhaus_live_state_path=spamhaus_live_state_path,
        dns_policy_path=dns_policy_path,
        fail2ban_live_state_path=fail2ban_live_state_path,
        nftables_live_state_path=nftables_live_state_path,
        now=now,
    )
    return augment_snapshot(snapshot, load_correlation(correlation_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", type=Path, default=base.FINAL.BASE.BASE.BASE.DEFAULT_NETWORK)
    parser.add_argument("--security", type=Path, default=base.FINAL.BASE.BASE.BASE.DEFAULT_SECURITY)
    parser.add_argument("--correlation", type=Path, default=base.FINAL.BASE.BASE.BASE.DEFAULT_CORRELATION)
    parser.add_argument("--operations", type=Path, default=base.FINAL.BASE.BASE.BASE.DEFAULT_OPERATIONS)
    parser.add_argument("--spamhaus", type=Path, default=base.FINAL.BASE.BASE.BASE.DEFAULT_SPAMHAUS)
    parser.add_argument("--spamhaus-live-state", type=Path, default=base.FINAL.BASE.BASE.BASE.DEFAULT_SPAMHAUS_LIVE_STATE)
    parser.add_argument("--dns-policy", type=Path, default=base.FINAL.BASE.BASE.DEFAULT_DNS_POLICY)
    parser.add_argument("--fail2ban-live-state", type=Path, default=base.FINAL.BASE.DEFAULT_FAIL2BAN_LIVE_STATE)
    parser.add_argument("--nftables-live-state", type=Path, default=base.FINAL.DEFAULT_NFTABLES_LIVE_STATE)
    parser.add_argument("--output", type=Path, default=base.FINAL.BASE.BASE.BASE.DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_snapshot(
        network_path=args.network,
        security_path=args.security,
        correlation_path=args.correlation,
        operations_path=args.operations,
        spamhaus_path=args.spamhaus,
        spamhaus_live_state_path=args.spamhaus_live_state,
        dns_policy_path=args.dns_policy,
        fail2ban_live_state_path=args.fail2ban_live_state,
        nftables_live_state_path=args.nftables_live_state,
    )
    base.FINAL.BASE.BASE.BASE.write_snapshot(snapshot, args.output)
    print(json.dumps({
        "ok": True,
        "output": str(args.output),
        "overall_state": snapshot["overall_state"],
        "network_sensor_state": snapshot.get("components", {}).get("network_sensor", {}).get("state", "absent"),
        "verified_enforcement_count": snapshot["summary"]["verified_enforcement_count"],
        "traffic_controls_changed": False,
    }))


if __name__ == "__main__":
    main()
