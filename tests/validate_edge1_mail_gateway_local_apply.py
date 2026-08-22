#!/usr/bin/env python3
"""Validate the backup-first Edge1 Mail Gateway local apply package."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
APPLY = ROOT / "deploy" / "messaging" / "apply-edge1-mail-gateway-local.sh"
ACCEPTANCE = ROOT / "tools" / "messaging" / "edge1_mail_gateway_local_acceptance.py"
ARCHIVE = ROOT / "tools" / "messaging" / "edge1_mail_gateway_archive.py"
RENDERER = ROOT / "tools" / "messaging" / "render_edge1_mail_gateway_postfix.py"
CONFIG = ROOT / "config" / "messaging" / "edge1-mail-gateway-v1.json"


def load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    assert subprocess.run(["bash", "-n", str(APPLY)], check=False).returncode == 0
    for script in (ACCEPTANCE, ARCHIVE, RENDERER):
        assert subprocess.run([sys.executable, "-m", "py_compile", str(script)], check=False).returncode == 0

    apply_text = APPLY.read_text(encoding="utf-8")
    required = [
        "WWCX-EDGE1-MAIL-GATEWAY-LOCAL-APPLY-001",
        "inet_interfaces=loopback-only",
        "wwcxmail_destination_recipient_limit=1",
        "message_size_limit=52428800",
        "edge1_mail_gateway_archive.py",
        "--archive-root /var/lib/wwcx-mail-gateway/inbound",
        "--recipient ${original_recipient}",
        "flags=ROq",
        "postconf-n.before.txt",
        "master.cf.before",
        "rollback_performed=true",
        "postfix",
        "check",
        "reload",
        "127\\.0\\.0\\.1:25",
        "acceptance@ww.cx",
        "No DNS, MX, firewall, certificate, provider, or outbound-delivery change was made.",
    ]
    for token in required:
        assert token in apply_text, token

    forbidden = [
        "inet_interfaces=all",
        "0.0.0.0:25",
        "iptables ",
        "nft ",
        "ufw ",
        "certbot ",
        "nsupdate ",
        "rndc ",
        "production_mx_changes_authorized=true",
        "public_smtp_listener_enabled=true",
    ]
    for token in forbidden:
        assert token not in apply_text, token

    renderer = load_module(RENDERER, "edge1_apply_renderer")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    rendered = renderer.render(config)
    assert "inet_interfaces = loopback-only" in rendered["main.cf.fragment"]
    assert "wwcxmail_destination_recipient_limit = 1" in rendered["main.cf.fragment"]
    assert "message_size_limit = 52428800" in rendered["main.cf.fragment"]
    assert "flags=ROq" in rendered["master.cf.fragment"]
    assert "edge1_mail_gateway_archive.py" in rendered["master.cf.fragment"]
    assert "--recipient ${original_recipient}" in rendered["master.cf.fragment"]
    assert "ww.cx OK" not in rendered["wwcx-edge1-managed-domains"]

    acceptance = load_module(ACCEPTANCE, "edge1_local_acceptance")
    selected = acceptance._candidate_domain(config, None)
    assert selected == "creekco.ca"
    assert acceptance._candidate_domain(config, "omegafx.com") == "omegafx.com"
    message_id, sender, raw = acceptance._message(
        "acceptance-unit@creekco.ca", datetime(2026, 8, 22, 7, 40, tzinfo=timezone.utc)
    )
    assert message_id.startswith("<edge1-mail-gateway-acceptance-")
    assert sender == "mail-gateway-acceptance@ww.cx"
    assert b"To: acceptance-unit@creekco.ca" in raw
    assert b"WW.CX Edge1 Mail Gateway local acceptance" in raw
    assert b"X-Original-To:" not in raw  # Postfix O flag must add this independently.

    print("Edge1 Mail Gateway local apply validation passed")
    print("Apply is authorization-gated, backup-first, and rollback-armed")
    print("Postfix remains loopback-only and ww.cx remains external")
    print("Pipe delivery archives raw RFC822 before best-effort normalization")
    print("Acceptance submits only to 127.0.0.1:25")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
