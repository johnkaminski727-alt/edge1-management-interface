#!/usr/bin/env python3
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "deploy" / "activate-suricata-alert-normalization.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "set -Eeuo pipefail",
    "be2880d49ab842b1876e6c2898f1acced6bb78f1",
    "validate_security_operations_cache.py",
    "validate_security_operations_normalization.py",
    "validate_security_operations_ui.py",
    "staged-security.json",
    "staged-correlation.json",
    "staged-network-defense.json",
    "wwcx-security-operations.service",
    "wwcx-security-correlation.service",
    "wwcx-network-defense.service",
    "wwcx.suricata-alert.v1",
    "verify-security-observability-live.sh",
    "traffic_controls_changed",
    "No IDS rules, DNS, firewall, routing, Fail2ban, proxy, or traffic controls were changed.",
)

missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit(f"Suricata normalization activator markers missing: {missing}")

forbidden = (
    "systemctl disable",
    "systemctl mask",
    "nft ",
    "iptables",
    "ufw ",
    "unbound-control",
    "suricata-update",
    "rm -rf",
    "git reset",
    "git clean",
    "git checkout",
)

present = [marker for marker in forbidden if marker in text]
if present:
    raise SystemExit(f"Suricata normalization activator contains forbidden mutations: {present}")

print("Suricata normalization activator validation passed")
