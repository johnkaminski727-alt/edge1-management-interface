#!/usr/bin/env python3
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "deploy" / "activate-suricata-collector-enrichment.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "set -Eeuo pipefail",
    "server/bigbird_ops_collect.py",
    "/usr/local/libexec/bigbird-ops-collect.py",
    "bigbird-ops-push.service",
    "bigbird-ops-push.timer",
    "validate_bigbird_ops_collector_suricata.py",
    "wwcx.suricata-source-alert.v1",
    "edge1-suricata-enrichment-r1",
    "activate-suricata-alert-normalization.sh",
    "source_port_count",
    "destination_port_count",
    "signature_id_count",
    "flow_id_count",
    "traffic_controls_changed",
    "collector_rolled_back=true",
    "No IDS rules, DNS, firewall, routing, Fail2ban, proxy, or traffic controls were changed.",
)

missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit(f"Suricata collector deployer markers missing: {missing}")

forbidden = (
    "systemctl disable",
    "systemctl mask",
    "nft ",
    "iptables",
    "ufw ",
    "unbound-control",
    "suricata-update",
    "systemctl restart suricata",
    "systemctl reload suricata",
    "rm -rf",
    "git reset",
    "git clean",
    "git checkout",
)

present = [marker for marker in forbidden if marker in text]
if present:
    raise SystemExit(f"Suricata collector deployer contains forbidden mutations: {present}")

print("Suricata collector deployer validation passed")
