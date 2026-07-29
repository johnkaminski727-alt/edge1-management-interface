#!/usr/bin/env python3
"""Validation for live Security Correlation and Network Defense acceptance."""

import datetime as dt
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "security" / "verify_security_observability.py"
WRAPPER_PATH = ROOT / "tools" / "security" / "verify-security-observability-live.sh"
SPEC = importlib.util.spec_from_file_location("verify_security_observability", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Security observability verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecurityObservabilityAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 7, 29, 6, 0, 0, tzinfo=dt.timezone.utc)
        generated = (self.now - dt.timedelta(seconds=30)).isoformat()
        self.correlation = {
            "schema_version": "1.0",
            "generated_at": generated,
            "read_only": True,
            "privacy": {
                "packet_payloads_included": False,
                "credentials_included": False,
                "private_keys_included": False,
                "raw_logs_included": False,
                "event_fields_minimized": True,
            },
            "summary": {
                "event_count": 4,
                "correlation_count": 1,
                "available_source_count": 4,
                "source_count": 4,
            },
        }
        self.network_defense = {
            "schema_version": "1.0",
            "generated_at": generated,
            "read_only": True,
            "traffic_controls_changed": False,
            "overall_state": "limited",
            "summary": {"available_source_count": 5, "source_count": 6},
            "sources": {
                "correlation": {
                    "available": True,
                    "stale": False,
                    "age_seconds": 30,
                    "detail": "loaded",
                }
            },
            "components": {"dns_policy": {"state": "not_staged"}},
            "dns_policy": {
                "enforcement_enabled": False,
                "enforcement_verified": False,
                "traffic_controls_changed": False,
                "requires_explicit_activation": True,
            },
        }

    def test_acceptance_passes_when_correlation_is_consumed(self):
        result = MODULE.validate_acceptance(
            self.correlation,
            self.network_defense,
            now=self.now,
            max_age_seconds=600,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["traffic_controls_changed"])
        self.assertEqual(result["correlation"]["events"], 4)
        self.assertEqual(result["network_defense"]["correlation_age_seconds"], 30)

    def test_acceptance_rejects_unconsumed_correlation(self):
        self.network_defense["sources"]["correlation"]["available"] = False
        with self.assertRaisesRegex(MODULE.AcceptanceError, "has not consumed"):
            MODULE.validate_acceptance(self.correlation, self.network_defense, now=self.now)

    def test_acceptance_rejects_stale_documents(self):
        self.correlation["generated_at"] = (self.now - dt.timedelta(seconds=601)).isoformat()
        with self.assertRaisesRegex(MODULE.AcceptanceError, "stale"):
            MODULE.validate_acceptance(
                self.correlation,
                self.network_defense,
                now=self.now,
                max_age_seconds=600,
            )

    def test_acceptance_rejects_control_or_privacy_overclaim(self):
        self.network_defense["traffic_controls_changed"] = True
        with self.assertRaisesRegex(MODULE.AcceptanceError, "traffic_controls_changed"):
            MODULE.validate_acceptance(self.correlation, self.network_defense, now=self.now)

        self.network_defense["traffic_controls_changed"] = False
        self.correlation["privacy"]["raw_logs_included"] = True
        with self.assertRaisesRegex(MODULE.AcceptanceError, "raw_logs_included"):
            MODULE.validate_acceptance(self.correlation, self.network_defense, now=self.now)

    def test_wrapper_is_read_only_and_uses_authoritative_endpoints(self):
        source = WRAPPER_PATH.read_text(encoding="utf-8")
        for token in (
            "$STATUS_URL/security-correlation.json",
            "$STATUS_URL/network-defense/data/network-defense.json",
            "Security Correlation is live and consumed by Network Defense.",
            "traffic_controls_changed=false",
            "accepted=true",
        ):
            self.assertIn(token, source)
        self.assertIsNone(
            re.search(
                r"systemctl\s+(?:start|stop|restart|reload|enable|disable|try-restart)",
                source,
                re.IGNORECASE,
            )
        )
        self.assertNotRegex(source, r"\b(?:nft|iptables|firewall-cmd|fail2ban-client|unbound-control)\b")


if __name__ == "__main__":
    unittest.main()
