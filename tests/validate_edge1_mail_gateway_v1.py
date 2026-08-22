#!/usr/bin/env python3
"""Validate the disabled-by-default Edge1 Mail Gateway v1 contract."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/messaging/edge1-mail-gateway-v1.json"


def main() -> int:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert data["contract"] == "wwcx.edge1-mail-gateway.v1"
    assert data["service_hostname"] == "mail.ww.cx"
    assert data["storage_root"] == "/var/lib/wwcx-mail-gateway"
    assert data["provenance_source"] == "edge1-mail-gateway-smtp"

    activation = data["activation"]
    assert activation == {
        "public_smtp_listener_enabled": False,
        "production_mx_changes_authorized": False,
        "outbound_delivery_enabled": False,
    }

    domains = data["domains"]
    expected_domains = {
        "ww.cx",
        "creekco.ca",
        "spiritcreekgardens.com",
        "scgardens.ca",
        "omegafx.com",
    }
    assert set(domains) == expected_domains

    ww = domains["ww.cx"]
    assert ww["mode"] == "stay_external"
    assert ww["migration_order"] is None
    assert ww["catch_all_enabled"] is False
    assert ww["archive_identity"] is None
    assert ww["retain_provider_fallback"] is True

    ordered = [
        ("creekco.ca", 1, "archive@creekco.ca"),
        ("spiritcreekgardens.com", 2, "archive@spiritcreekgardens.com"),
        ("scgardens.ca", 3, "archive@scgardens.ca"),
        ("omegafx.com", 4, "archive@omegafx.com"),
    ]
    for domain, order, archive_identity in ordered:
        entry = domains[domain]
        assert entry["mode"] == "candidate"
        assert entry["migration_order"] == order
        assert entry["catch_all_enabled"] is True
        assert entry["archive_identity"] == archive_identity
        assert entry["retain_provider_fallback"] is True

    print("Edge1 Mail Gateway v1 configuration is disabled and internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
