#!/usr/bin/env python3
"""Static checks for the staged, fail-closed Spamhaus JSON preflight."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "tools/networking/spamhaus-nft-update.sh"
INSTALLER = ROOT / "tools/networking/install-spamhaus-filter.sh"
PARSER = ROOT / "tools/networking/spamhaus_feed_candidate.py"
SERVICE = ROOT / "tools/networking/systemd/bigbird-spamhaus-filter.service"
TIMER = ROOT / "tools/networking/systemd/bigbird-spamhaus-filter.timer"
SMOKE = ROOT / "tools/networking/spamhaus-filter-smoke-test.sh"
MODULE_DOC = ROOT / "docs/modules/spamhaus-filtering.md"
STAGING_DOC = ROOT / "docs/security/spamhaus-json-staging-gate-20260927.md"

required = [UPDATER, INSTALLER, PARSER, SERVICE, TIMER, SMOKE, MODULE_DOC, STAGING_DOC]
missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
assert not missing, f"Missing Spamhaus module files: {', '.join(missing)}"

updater = UPDATER.read_text(encoding="utf-8")
parser = PARSER.read_text(encoding="utf-8")
installer = INSTALLER.read_text(encoding="utf-8")
service = SERVICE.read_text(encoding="utf-8")

# The updater validates current official feeds but cannot apply a production ruleset.
assert "drop_v4.json" in updater and "drop_v6.json" in updater
assert "--check-only" in updater and '--apply' not in updater
assert '"$NFT" --check --file "$WORK/candidate.nft"' in updater
assert '"$NFT" -f' not in updater and '"$NFT" --file' not in updater
assert "nft --check" not in installer
assert "exit 1" in installer
assert "systemctl" not in installer
assert "ipaddress.collapse_addresses" in parser
assert "MAX_FEED_AGE" in parser
assert "priority -110" in parser
assert "Type=oneshot" in service
assert "ExecStart=/usr/local/sbin/bigbird-spamhaus-nft-update" in service

print("PASS: Spamhaus staging is JSON-only, check-only, and installer blocked")
