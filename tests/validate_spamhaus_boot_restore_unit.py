#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"deploy/systemd/edge1-spamhaus-restore.service"
t=p.read_text()
assert "chronyc waitsync 30 0.1" in t
assert "spamhaus_boot_preflight.py" in t
assert "spamhaus_boot_restore.py" in t and "--execute" in t
assert "After=local-fs.target network-online.target chrony.service ufw.service crowdsec.service crowdsec-firewall-bouncer.service" in t
assert not any(x.strip()=="[Install]" for x in t.splitlines())
assert "nftables.service" not in t
assert not any("systemctl" in line for line in t.splitlines() if line.strip() and not line.lstrip().startswith("#"))
assert "bigbird-spamhaus-filter.timer" not in t
print("PASS: staged restore unit is ordered, pinned, and not enableable")
