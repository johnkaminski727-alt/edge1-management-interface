#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from edge1_snmp_api import approved_profile_version, validate_device_profile
from edge1_snmp_services import DiscoveryService


class Profile:
    def __init__(self, version: str):
        self.version = version


class Resolver:
    def __init__(self, version: str):
        self.version = version

    def load(self, reference: str):
        if reference != "test-profile":
            raise ValueError("unknown profile")
        return Profile(self.version)


class FakeNet:
    def __init__(self, version: str):
        self.resolver = Resolver(version)

    def query(self, tool, address, port, profile_ref, oids, **kwargs):
        return {oid: f"value-{index}" for index, oid in enumerate(oids)}


CONFIG = {
    "polling": {"interval_seconds": 300, "concurrency": 4},
    "discovery": {"allowed_cidrs": ["10.10.0.0/16"], "max_hosts": 32, "allow_public": False},
}


class DiscoverySecurityTests(unittest.TestCase):
    def test_v3_profile_is_accepted(self):
        self.assertEqual(approved_profile_version("test-profile", net=FakeNet("3")), "3")

    def test_legacy_profile_is_denied_without_explicit_approval(self):
        with self.assertRaisesRegex(ValueError, "explicit legacy_protocol_approved"):
            approved_profile_version("test-profile", net=FakeNet("2c"))
        self.assertEqual(
            approved_profile_version("test-profile", legacy_protocol_approved=True, net=FakeNet("2c")),
            "2c",
        )

    def test_device_declared_version_must_match_profile(self):
        payload = {"credential_reference": "test-profile", "snmp_version": "3", "legacy_protocol_approved": True}
        with self.assertRaisesRegex(ValueError, "does not match credential profile"):
            validate_device_profile(payload, net=FakeNet("2c"))

    def test_discovery_reports_actual_profile_version(self):
        preview = asyncio.run(DiscoveryService(FakeNet("2c")).scan(
            "10.10.2.0/30", "test-profile", config=CONFIG, dry_run=True,
        ))
        self.assertEqual(preview["snmp_version"], "2c")
        result = asyncio.run(DiscoveryService(FakeNet("3")).scan(
            "10.10.2.0/30", "test-profile", config=CONFIG, dry_run=False,
        ))
        self.assertEqual(result["snmp_version"], "3")
        self.assertTrue(all(device["snmp_version"] == "3" for device in result["devices"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
