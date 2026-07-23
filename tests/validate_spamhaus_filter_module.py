#!/usr/bin/env python3
"""Static validation for the repository-managed Spamhaus filtering module."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "tools/networking/spamhaus-nft-update.sh"
INSTALLER = ROOT / "tools/networking/install-spamhaus-filter.sh"
SERVICE = ROOT / "tools/networking/systemd/bigbird-spamhaus-filter.service"
TIMER = ROOT / "tools/networking/systemd/bigbird-spamhaus-filter.timer"
SMOKE = ROOT / "tools/networking/spamhaus-filter-smoke-test.sh"
MODULE_DOC = ROOT / "docs/modules/spamhaus-filtering.md"

required = [UPDATER, INSTALLER, SERVICE, TIMER, SMOKE, MODULE_DOC]
missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"Missing Spamhaus module files: {', '.join(missing)}")

updater = UPDATER.read_text(encoding="utf-8")
assert 'ipaddress.collapse_addresses' in updater
assert 'delete table {family} {table}' in updater
assert '"$NFT" -c -f "$work_dir/spamhaus.nft"' in updater
assert 'refusing suspicious network' in updater
assert 'refusing to change nftables' in updater

installer = INSTALLER.read_text(encoding="utf-8")
assert "bigbird-spamhaus-filter.service" in installer
assert "bigbird-spamhaus-filter.timer" in installer
assert "spamhaus-nft-update.sh" in installer

service = SERVICE.read_text(encoding="utf-8")
assert "Type=oneshot" in service
assert "ExecStart=/usr/local/sbin/bigbird-spamhaus-nft-update" in service

print("Spamhaus filtering module validation passed")
