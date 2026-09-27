#!/usr/bin/env python3
"""Assignment 240: static contract for staged, non-enableable restore unit."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
unit = (root / "deploy/systemd/edge1-spamhaus-restore.service").read_text()
guard = (root / "tools/networking/spamhaus_guarded_boot_restore.py").read_text()
assert "spamhaus_guarded_boot_restore.py --execute" in unit
assert "Requires=chrony.service ssh.service ufw.service crowdsec.service crowdsec-firewall-bouncer.service" in unit
assert "After=local-fs.target network-online.target" in unit
assert "[Install]" not in [line.strip() for line in unit.splitlines()]
assert "nftables.service" not in unit
assert "spamhaus_scoped_recovery.py" in guard
assert "arm_rollback()" in guard
assert guard.index("arm_rollback()\n    #") < guard.index("require([NFT, \"--file\"")
assert "MAX_FEED_AGE" not in guard or "72" not in guard  # parser owns freshness
assert "--on-active=180s" in guard
print("PASS: guarded restore unit staged, rollback-before-apply, no Install section")
