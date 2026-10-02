#!/usr/bin/env python3
"""Mocked boot readiness gate tests; no host services/nftables accessed."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools/networking/spamhaus_boot_readiness.py"
SPEC = importlib.util.spec_from_file_location("spamhaus_boot_readiness", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeRunner:
    def __init__(self, clock=True, leap="Normal", stopped=None,
                 existing=False, listing_error=False, malformed=False):
        self.clock, self.leap, self.stopped = clock, leap, stopped
        self.existing, self.listing_error, self.malformed = existing, listing_error, malformed
        self.commands = []

    def __call__(self, args):
        args = list(args)
        self.commands.append(args)
        if args == ["/usr/bin/timedatectl", "show", "-p", "NTPSynchronized", "--value"]:
            return subprocess.CompletedProcess(args, 0, "yes\n" if self.clock else "no\n", "")
        if args == ["/usr/bin/chronyc", "tracking"]:
            return subprocess.CompletedProcess(args, 0, f"Leap status     : {self.leap}\n", "")
        if args[:2] == ["/usr/bin/systemctl", "is-active"]:
            active = args[2] != self.stopped
            return subprocess.CompletedProcess(args, 0 if active else 3,
                                               "active\n" if active else "inactive\n", "")
        if args == [MODULE.NFT, "list", "table", "inet", "bigbird_spamhaus"]:
            return subprocess.CompletedProcess(args, 0 if self.existing else 1, "", "")
        if args == [MODULE.NFT, "-j", "list", "tables"]:
            if self.listing_error:
                return subprocess.CompletedProcess(args, 1, "", "simulated error")
            return subprocess.CompletedProcess(
                args, 0, "{malformed" if self.malformed else json.dumps({
                    "nftables": [{"table": {"family": "inet", "name": "ufw"}}]
                }), ""
            )
        raise AssertionError("Unexpected command: " + str(args))


class BootReadinessTests(unittest.TestCase):
    def test_eligible_when_clock_services_ready_and_table_absent(self):
        runner = FakeRunner()
        self.assertEqual(MODULE.inspect(runner), "eligible_for_separate_candidate_validation")
        self.assertFalse(any("delete" in command or "--file" in command for command in runner.commands))

    def test_already_active_is_not_replaced(self):
        runner = FakeRunner(existing=True)
        self.assertEqual(MODULE.inspect(runner), "already_active")
        self.assertEqual(len([c for c in runner.commands if c[0] == MODULE.NFT]), 1)

    def test_unsynchronized_clock_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "clock"):
            MODULE.inspect(FakeRunner(clock=False))

    def test_chrony_not_normal_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "Chrony"):
            MODULE.inspect(FakeRunner(leap="Not synchronised"))

    def test_inactive_firewall_bouncer_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "crowdsec-firewall-bouncer"):
            MODULE.inspect(FakeRunner(stopped="crowdsec-firewall-bouncer.service"))

    def test_nft_inventory_error_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "verify"):
            MODULE.inspect(FakeRunner(listing_error=True))

    def test_malformed_nft_inventory_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "interpret"):
            MODULE.inspect(FakeRunner(malformed=True))


if __name__ == "__main__":
    unittest.main()
