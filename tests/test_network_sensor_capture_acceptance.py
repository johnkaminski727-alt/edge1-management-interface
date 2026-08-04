#!/usr/bin/env python3
"""Tests for the live network-sensor capture acceptance check."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import network_sensor_capture_acceptance as acceptance  # noqa: E402


class CaptureAcceptanceTests(unittest.TestCase):
    def test_latest_current_run_stats_ignores_stale_rows(self) -> None:
        started_at = acceptance.parse_timestamp("2026-08-04T23:25:00Z")
        rows = [
            {
                "timestamp": "2026-08-04T23:24:00.000000+0000",
                "event_type": "stats",
                "stats": {"capture": {"kernel_packets": 999}, "decoder": {"pkts": 999, "bytes": 999}},
            },
            {
                "timestamp": "2026-08-04T23:25:30.816516+0000",
                "event_type": "stats",
                "stats": {
                    "capture": {"kernel_packets": 353, "kernel_drops": 0},
                    "decoder": {"pkts": 417, "bytes": 230412},
                },
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            eve = pathlib.Path(temporary) / "eve.json"
            eve.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            latest = acceptance.latest_current_run_stats(eve, started_at)
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["kernel_packets"], 353)
        self.assertEqual(latest["decoder_packets"], 417)
        self.assertEqual(latest["decoder_bytes"], 230412)

    def test_evaluate_rejects_zero_suricata_with_interface_traffic(self) -> None:
        result = acceptance.evaluate(100, 150, None)
        self.assertEqual(result["result"], "fail-active-interface-suricata-zero")
        self.assertFalse(result["capture_validated"])
        self.assertEqual(result["interface_packets_delta"], 50)

    def test_evaluate_passes_nonzero_suricata(self) -> None:
        result = acceptance.evaluate(
            100,
            150,
            {
                "timestamp": "2026-08-04T23:25:30+00:00",
                "kernel_packets": 353,
                "kernel_drops": 0,
                "decoder_packets": 417,
                "decoder_bytes": 230412,
            },
        )
        self.assertEqual(result["result"], "pass")
        self.assertTrue(result["capture_validated"])

    def test_no_interface_traffic_is_inconclusive_not_failure(self) -> None:
        result = acceptance.evaluate(100, 100, None)
        self.assertEqual(result["result"], "inconclusive-no-interface-traffic")

    def test_interface_packet_count_reads_rx_and_tx(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            statistics = pathlib.Path(temporary) / "wg0" / "statistics"
            statistics.mkdir(parents=True)
            (statistics / "rx_packets").write_text("12\n", encoding="ascii")
            (statistics / "tx_packets").write_text("30\n", encoding="ascii")
            self.assertEqual(acceptance.interface_packet_count("wg0", pathlib.Path(temporary)), 42)


if __name__ == "__main__":
    unittest.main()
