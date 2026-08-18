import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "server"))
import bigbird_camera_discovery as discovery


class Tests(unittest.TestCase):
    def test_normalizes_only_private_non_loopback_neighbors(self):
        payload = [
            {"dst": "192.168.1.20", "dev": "eth0", "lladdr": "AA:BB:CC:DD:EE:FF", "state": ["REACHABLE"]},
            {"dst": "127.0.0.1", "dev": "lo", "state": ["PERMANENT"]},
            {"dst": "8.8.8.8", "dev": "eth0", "state": ["STALE"]},
        ]
        rows = discovery.normalize_neighbors(payload)
        self.assertEqual(rows, [{"ip": "192.168.1.20", "dev": "eth0", "state": ["REACHABLE"], "mac": "aa:bb:cc:dd:ee:ff"}])

    def test_rejects_unobserved_candidate(self):
        with self.assertRaises(discovery.DiscoveryError):
            discovery.probe_observed_candidate("192.168.1.21", [{"ip": "192.168.1.20"}])

    def test_rejects_global_candidate(self):
        with self.assertRaises(discovery.DiscoveryError):
            discovery.probe_observed_candidate("8.8.8.8", [{"ip": "8.8.8.8"}])

    def test_probe_uses_fixed_port_allowlist(self):
        neighbors = [{"ip": "192.168.1.20"}]
        with mock.patch.object(discovery, "_probe_tcp", return_value=False) as probe:
            result = discovery.probe_observed_candidate("192.168.1.20", neighbors)
        self.assertEqual([x["port"] for x in result["ports"]], list(discovery.PROBE_PORTS))
        self.assertEqual([c.args[1] for c in probe.call_args_list], list(discovery.PROBE_PORTS))

    def test_summary_does_not_echo_private_identifiers(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = pathlib.Path(td) / "e.json"
            evidence.write_text(json.dumps({"neighbors": [{"ip": "192.168.1.20", "mac": "aa:bb"}]}))
            record = {"neighbors": [{"ip": "192.168.1.20", "mac": "aa:bb"}], "probe": None}
            summary = discovery.sanitized_summary(record, evidence)
            encoded = json.dumps(summary)
            self.assertNotIn("192.168.1.20", encoded)
            self.assertNotIn("aa:bb", encoded)
            self.assertFalse(summary["private_identifiers_in_stdout"])


if __name__ == "__main__":
    unittest.main()
