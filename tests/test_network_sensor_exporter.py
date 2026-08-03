#!/usr/bin/env python3
import datetime as dt
import importlib.util
import json
import stat
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "server" / "network_sensor_exporter.py"
SPEC = importlib.util.spec_from_file_location("network_sensor_exporter", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class NetworkSensorExporterTests(unittest.TestCase):
    def test_owner_full_snapshot_and_public_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eve = root / "eve.json"
            rows = [
                {"timestamp": "2026-08-03T01:00:00Z", "event_type": "dns", "src_ip": "192.168.1.10", "dest_ip": "1.1.1.1", "dest_port": 53, "proto": "UDP", "dns": {"rrname": "example.com"}},
                {"timestamp": "2026-08-03T01:00:01Z", "event_type": "tls", "src_ip": "192.168.1.10", "dest_ip": "203.0.113.7", "dest_port": 443, "proto": "TCP", "app_proto": "tls", "tls": {"sni": "api.example.com"}},
                {"timestamp": "2026-08-03T01:00:02Z", "event_type": "flow", "src_ip": "192.168.1.10", "dest_ip": "203.0.113.7", "dest_port": 443, "flow": {"bytes_toserver": 100, "bytes_toclient": 900}},
                {"timestamp": "2026-08-03T01:00:03Z", "event_type": "alert", "src_ip": "203.0.113.7", "dest_ip": "192.168.1.10", "alert": {"signature": "Synthetic alert"}, "payload": "retained in restricted sample"},
            ]
            eve.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            zeek = root / "zeek"
            zeek.mkdir()
            (zeek / "http.log").write_text(json.dumps({"id.orig_h": "192.168.1.10", "id.resp_h": "198.51.100.5", "id.resp_p": 80, "host": "plain.example", "uri": "/private", "method": "POST"}) + "\n", encoding="utf-8")
            pcap = root / "pcap"
            pcap.mkdir()
            (pcap / "sample.pcap").write_bytes(b"pcap")
            extracted = root / "extracted"
            extracted.mkdir()

            restricted, public = MODULE.build_snapshot(
                eve, zeek, pcap, extracted, "enp3s0",
                MODULE.parse_networks(MODULE.DEFAULT_INTERNAL),
                now=dt.datetime(2026, 8, 3, 2, 0, tzinfo=dt.timezone.utc),
            )
            self.assertEqual(restricted["contract"], MODULE.CONTRACT)
            self.assertTrue(restricted["capture"]["full_packet_capture"])
            self.assertEqual(restricted["totals"]["flow_bytes_to_external"], 100)
            self.assertEqual(restricted["totals"]["flow_bytes_from_external"], 900)
            self.assertEqual(restricted["recent_suricata_events"][-1]["payload"], "retained in restricted sample")
            self.assertNotIn("recent_suricata_events", public)
            self.assertNotIn("internal_sources", public["top"])
            self.assertNotIn("external_destinations", public["top"])
            self.assertNotIn("dns_queries", public["top"])
            self.assertNotIn("tls_server_names", public["top"])
            self.assertNotIn("http_hosts", public["top"])

    def test_atomic_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            restricted = Path(tmp) / "restricted.json"
            public = Path(tmp) / "public.json"
            MODULE.atomic_write(restricted, {"ok": True}, 0o600)
            MODULE.atomic_write(public, {"ok": True}, 0o644)
            self.assertEqual(stat.S_IMODE(restricted.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(public.stat().st_mode), 0o644)
            self.assertTrue(json.loads(restricted.read_text())["ok"])

    def test_no_network_or_shell_execution(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for token in ("subprocess", "socket", "requests", "urllib", "os.system", "Popen("):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
