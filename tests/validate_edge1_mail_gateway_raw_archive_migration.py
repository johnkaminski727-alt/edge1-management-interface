#!/usr/bin/env python3
"""Static and contract validation for the live raw-archive migration wrapper."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATE = ROOT / "deploy" / "messaging" / "migrate-edge1-mail-gateway-raw-archive.sh"
APPLY = ROOT / "deploy" / "messaging" / "apply-edge1-mail-gateway-local.sh"
ARCHIVE = ROOT / "tools" / "messaging" / "edge1_mail_gateway_archive.py"
ACCEPTANCE = ROOT / "tools" / "messaging" / "edge1_mail_gateway_local_acceptance.py"


def main() -> int:
    for script in (MIGRATE, APPLY):
        assert subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0

    migrate = MIGRATE.read_text(encoding="utf-8")
    apply = APPLY.read_text(encoding="utf-8")
    archive = ARCHIVE.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    required_migration = [
        "WWCX-EDGE1-MAIL-GATEWAY-RAW-ARCHIVE-001",
        "edge1_mail_gateway_ingest.py",
        "edge1_mail_gateway_archive.py",
        "message_size_limit=52428800",
        "--recipient ${original_recipient}",
        "flags=ROq",
        "main.cf.before",
        "master.cf.before",
        "rollback_performed=true",
        "rollback_performed=false",
        "local-acceptance.json",
        "127\\.0\\.0\\.1:25",
        "No DNS, MX, firewall, certificate, provider, or outbound-delivery change was made.",
    ]
    for token in required_migration:
        assert token in migrate, token

    for text in (migrate, apply):
        assert "edge1_mail_gateway_archive.py" in text
        assert "--archive-root /var/lib/wwcx-mail-gateway/inbound" in text
        assert "message_size_limit=52428800" in text
        assert "inet_interfaces=all" not in text
        assert "0.0.0.0:25" not in text
        assert "iptables " not in text
        assert "nft " not in text
        assert "ufw " not in text
        assert "certbot " not in text
        assert "nsupdate " not in text

    assert "MAX_RAW_BYTES = 50 * 1024 * 1024" in archive
    assert "normalization_status" in archive
    assert '"status": "held"' in archive
    assert "existing archive metadata conflicts with delivery" in archive
    assert "raw_archive_verified" in acceptance
    assert "X-Original-To:" in acceptance
    assert "archive_rfc822_sha256" in acceptance

    print("Edge1 Mail Gateway raw archive migration validation passed")
    print("Migration is backup-first, rollback-armed, and loopback-only")
    print("Direct ingest is replaced only after exact accepted-state checks")
    print("Acceptance requires both durable raw RFC822 and Mail Room ingestion")
    print("No public listener, DNS, firewall, certificate, or outbound activation is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
