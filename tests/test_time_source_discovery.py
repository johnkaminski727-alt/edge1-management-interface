#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "time_authority"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import discover_edge1_time_sources as discovery  # noqa: E402


class TimeSourceDiscoveryTests(unittest.TestCase):
    def test_selected_network_source(self):
        text = """
MS Name/IP address         Stratum Poll Reach LastRx Last sample
===============================================================================
^+ 192.0.2.1                     1   6   377    12    +10us[  +20us] +/-  1ms
^* 198.51.100.2                  1   6   377    11     -2us[   -3us] +/-  1ms
"""
        self.assertEqual(
            discovery.parse_selected_chrony_source(text),
            {
                "type": "network",
                "source": "198.51.100.2",
                "raw": "^* 198.51.100.2                  1   6   377    11     -2us[   -3us] +/-  1ms",
            },
        )

    def test_selected_refclock_source(self):
        text = "#* PPS                           0   4   377     8     +0ns[   +0ns] +/- 100ns"
        selected = discovery.parse_selected_chrony_source(text)
        self.assertEqual(selected["type"], "refclock")
        self.assertEqual(selected["source"], "PPS")

    def test_parse_networkd_ntp_servers(self):
        text = "NTP=192.0.2.10 192.0.2.11\nDNS=192.0.2.53\n"
        self.assertEqual(
            discovery.parse_advertised_ntp_servers(text),
            {"192.0.2.10", "192.0.2.11"},
        )

    def test_parse_dhclient_ntp_servers(self):
        text = "option ntp-servers 198.51.100.4, 198.51.100.5;"
        self.assertEqual(
            discovery.parse_advertised_ntp_servers(text),
            {"198.51.100.4", "198.51.100.5"},
        )

    def test_documented_gnss_requires_live_stratum_one(self):
        source = {
            "reference_type_documented": "GNSS (GPS, GLONASS, Galileo)",
        }
        records = [
            {
                "reachable": True,
                "stratum": 1,
                "refid": "PPS",
                "resolved_address": "192.0.2.1",
                "rtt_ms": 0.8,
                "clock_offset_ms": 0.03,
                "root_dispersion_ms": 0.2,
                "expectation_ok": True,
                "error": None,
            },
            {
                "reachable": True,
                "stratum": 1,
                "refid": "PPS",
                "resolved_address": "192.0.2.1",
                "rtt_ms": 1.0,
                "clock_offset_ms": 0.01,
                "root_dispersion_ms": 0.3,
                "expectation_ok": True,
                "error": None,
            },
        ]
        summary = discovery.summarize_samples(source, records)
        self.assertEqual(summary["dominant_stratum"], 1)
        self.assertEqual(summary["median_rtt_ms"], 0.9)
        self.assertEqual(
            summary["gnss_evidence"]["classification"],
            "documented-reference-plus-live-stratum1",
        )

    def test_packet_refid_is_only_a_hint(self):
        source = {}
        records = [
            {
                "reachable": True,
                "stratum": 1,
                "refid": "GPS",
                "resolved_address": "192.0.2.2",
                "rtt_ms": 1.2,
                "clock_offset_ms": 0.0,
                "root_dispersion_ms": 0.1,
                "expectation_ok": True,
                "error": None,
            }
        ]
        summary = discovery.summarize_samples(source, records)
        self.assertEqual(
            summary["gnss_evidence"]["classification"],
            "packet-refid-hint",
        )
        self.assertIn("hint", summary["gnss_evidence"]["reason"].lower())


if __name__ == "__main__":
    unittest.main()
