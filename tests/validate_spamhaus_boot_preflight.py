#!/usr/bin/env python3
"""No-network, no-nft tests for pinned Spamhaus boot preflight."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/networking/spamhaus_boot_preflight.py"
PARSER = ROOT / "tools/networking/spamhaus_feed_candidate.py"
SPEC = importlib.util.spec_from_file_location("spamhaus_boot_preflight", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BootPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name) / "stage"
        self.stage.mkdir(mode=0o700)
        stamp = int(dt.datetime.now(dt.timezone.utc).timestamp())
        (self.stage / "drop_v4.json").write_text(
            '{"cidr":"8.8.8.0/24"}\n' + '{"timestamp":' + str(stamp) + '}\n'
        )
        (self.stage / "drop_v6.json").write_text(
            '{"cidr":"2001:4860::/32"}\n' + '{"timestamp":' + str(stamp) + '}\n'
        )
        (self.stage / "spamhaus-candidate.nft").write_text(
            "table inet bigbird_spamhaus {\n"
            "  set drop4 {\n    type ipv4_addr\n    flags interval\n"
            "    elements = {\n      8.8.8.0/24\n    }\n  }\n"
            "  set drop6 {\n    type ipv6_addr\n    flags interval\n"
            "    elements = {\n      2001:4860::/32\n    }\n  }\n"
            "  chain input {\n    type filter hook input priority -110; policy accept;\n"
            "    ip saddr @drop4 counter drop\n    ip6 saddr @drop6 counter drop\n  }\n"
            "  chain forward {\n    type filter hook forward priority -110; policy accept;\n"
            "    ip saddr @drop4 counter drop\n    ip6 saddr @drop6 counter drop\n  }\n}\n"
        )
        (self.stage / "spamhaus_scoped_recovery.py").write_bytes(b"reviewed-recovery-copy\n")
        (self.stage / "source-commit.txt").write_text("reviewed-sha\n")
        (self.stage / "previous-checkpoint-path.txt").write_text("/protected/checkpoint\n")
        self.recovery = Path(self.temp.name) / "recovery.py"
        self.recovery.write_bytes(b"reviewed-recovery-copy\n")
        self.rehash()

    def rehash(self):
        names = MODULE.REQUIRED
        (self.stage / "SHA256SUMS").write_text("".join(
            hashlib.sha256((self.stage / name).read_bytes()).hexdigest()
            + "  " + name + "\n" for name in names
        ))

    def check(self):
        return MODULE.preflight(self.stage, PARSER, self.recovery)

    def test_valid_candidate(self):
        self.assertEqual(self.check()["ipv4_unique"], 1)
        self.assertEqual(self.check()["ipv6_unique"], 1)

    def test_tampered_file_rejected(self):
        (self.stage / "drop_v4.json").write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.check()

    def test_stale_feed_rejected(self):
        stamp = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=73)).timestamp())
        (self.stage / "drop_v6.json").write_text(
            '{"cidr":"2001:4860::/32"}\n' + '{"timestamp":' + str(stamp) + '}\n'
        )
        self.rehash()
        with self.assertRaisesRegex(ValueError, "age"):
            self.check()

    def test_wrong_candidate_rejected_even_if_rehashed(self):
        (self.stage / "spamhaus-candidate.nft").write_text("table inet wrong {}\n")
        self.rehash()
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.check()

    def test_recovery_mismatch_rejected(self):
        self.recovery.write_bytes(b"different\n")
        with self.assertRaisesRegex(ValueError, "recovery"):
            self.check()

    def test_manifest_duplicate_rejected(self):
        manifest = self.stage / "SHA256SUMS"
        manifest.write_text(manifest.read_text() + manifest.read_text().splitlines()[0] + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.check()


if __name__ == "__main__":
    unittest.main()
