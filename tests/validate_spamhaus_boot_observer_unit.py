#!/usr/bin/env python3
"""Guardrails: the proposed systemd boot observer is check-only and not enableable."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy/systemd/edge1-spamhaus-boot-preflight.service"
text = UNIT.read_text(encoding="utf-8")
assert "[Service]" in text and "Type=oneshot" in text
assert "User=root" in text and "UMask=0077" in text
assert "NoNewPrivileges=true" in text and "ProtectSystem=strict" in text
assert "spamhaus_boot_preflight.py" in text
assert "--stage /var/lib/edge1-spamhaus/boot-candidate" in text
assert "After=local-fs.target" in text
assert "[Install]" not in text
assert "nft " not in text and "/usr/sbin/nft" not in text
assert "--execute" not in text and "--apply" not in text
assert "ExecStart=" in text and "ExecStartPre=" not in text
assert "systemctl " not in text
print("PASS: Spamhaus boot observer unit is check-only, uninstalled and not enableable")
