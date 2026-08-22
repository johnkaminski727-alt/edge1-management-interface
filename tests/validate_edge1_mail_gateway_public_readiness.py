#!/usr/bin/env python3
"""Validate the read-only Edge1 Mail Gateway public-ingress readiness package."""

from __future__ import annotations

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "messaging" / "prepare-edge1-mail-gateway-public-readiness.sh"
CONFIG = ROOT / "config" / "messaging" / "edge1-mail-gateway-v1.json"


def main() -> int:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], check=False).returncode == 0

    text = SCRIPT.read_text(encoding="utf-8")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert config["service_hostname"] == "mail.ww.cx"
    assert config["activation"] == {
        "public_smtp_listener_enabled": False,
        "production_mx_changes_authorized": False,
        "outbound_delivery_enabled": False,
    }
    assert config["domains"]["ww.cx"]["mode"] == "stay_external"
    assert config["domains"]["ww.cx"]["catch_all_enabled"] is False

    required = [
        "wwcx.edge1-mail-gateway-public-readiness.v1",
        "mail.ww.cx",
        "edge1_mail_gateway_archive.py",
        "--recipient ${original_recipient}",
        "reject_unauth_destination",
        "wwcxmail_destination_recipient_limit",
        "52428800",
        "relay_domains must remain empty",
        "TCP/25 is already exposed outside loopback",
        "wwcx-mail-gateway:wwcx-mail-gateway 700",
        "getent",
        "ahostsv4",
        "dns_a_points_to_edge1",
        "ptr_forward_confirms",
        "DNS:$SERVICE_HOSTNAME",
        "tls_mail_ww_cx_ready",
        "nft",
        "list ruleset",
        "postfix-queue.txt",
        "storage-disk.txt",
        "public_listener_activation_authorized=no",
        "firewall_change_authorized=no",
        "certificate_change_authorized=no",
        "production_dns_mx_change_authorized=no",
        "external_tcp25_probe=pending_until_public_listener_authorized",
        "Do not migrate ww.cx",
    ]
    for token in required:
        assert token in text, token

    forbidden = [
        '"$POSTCONF_BIN" -e',
        '"$POSTCONF_BIN" -M -e',
        "postfix reload",
        "postfix restart",
        "systemctl restart",
        "systemctl reload",
        "nft add",
        "nft insert",
        "nft delete",
        "iptables ",
        "ufw allow",
        "ufw delete",
        "certbot ",
        "nsupdate ",
        "rndc ",
        "git pull",
        "git fetch",
        "openssl pkey",
        "openssl rsa",
    ]
    for token in forbidden:
        assert token not in text, token

    assert "inet_interfaces = all" not in text
    assert "0.0.0.0:25" not in text
    assert "public_smtp_listener_enabled\": true" not in text
    assert "production_mx_changes_authorized\": true" not in text

    print("Edge1 Mail Gateway public readiness validation passed")
    print("Preflight is evidence-only and preserves loopback-only SMTP")
    print("DNS, PTR, TLS, firewall, external probe, and MX remain separate gates")
    print("ww.cx remains external and outbound delivery remains disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
