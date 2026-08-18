#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from edge1_snmp_incidents import correlate_recent
from edge1_snmp_platform import CredentialResolver, add_device, connect_db
from edge1_snmp_services import add_topology_link, ensure_extended_schema, sync_interfaces
from edge1_snmp_set import execute_set


class IncidentAndSetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.conn = connect_db(self.root / "snmp.db")
        ensure_extended_schema(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _profile(self, name="v3"):
        profiles = self.root / "profiles"
        profiles.mkdir(exist_ok=True)
        path = profiles / f"{name}.json"
        path.write_text(
            '{"version":"3","username":"tester","auth_protocol":"SHA",'
            '"auth_password":"dummy-auth","priv_protocol":"AES","priv_password":"dummy-priv"}',
            encoding="utf-8",
        )
        os.chmod(path, 0o600)
        return CredentialResolver(profiles)

    def test_confirmed_topology_increases_correlation_confidence(self):
        upstream = add_device(self.conn, {
            "display_name": "switch-01", "management_address": "10.0.0.1", "credential_reference": "sw-v3"
        })
        downstream = add_device(self.conn, {
            "display_name": "router-01", "management_address": "10.0.0.2", "credential_reference": "r-v3"
        })
        self.conn.execute("UPDATE devices SET status='offline' WHERE device_id=?", (downstream["device_id"],))
        sync_interfaces(self.conn, upstream["device_id"], [{
            "if_index": 24, "if_name": "Gi0/24", "if_descr": "uplink", "if_alias": "router-01",
            "if_type": 6, "admin_status": 1, "oper_status": 2, "speed_bps": 1000000000, "counters": {}
        }])
        add_topology_link(
            self.conn, local_device_id=upstream["device_id"], local_if_index=24,
            remote_device_id=downstream["device_id"], remote_identifier="router-01",
            remote_port="eth0", evidence_type="LLDP", confidence="confirmed", evidence={"source": "LLDP-MIB"},
        )
        incidents = correlate_recent(self.conn)
        incident = next(x for x in incidents if x["subject_device_id"] == downstream["device_id"])
        self.assertIn(incident["confidence"], {"medium", "high"})
        self.assertIn("confirmed topology link", incident["ai_inference"].lower())
        self.assertTrue(any(x["type"] == "confirmed_topology_link" for x in incident["observed_facts"]))

    def test_inferred_link_remains_low_confidence(self):
        a = add_device(self.conn, {"display_name": "a", "management_address": "10.0.1.1", "credential_reference": "a-v3"})
        b = add_device(self.conn, {"display_name": "b", "management_address": "10.0.1.2", "credential_reference": "b-v3"})
        self.conn.execute("UPDATE devices SET status='offline' WHERE device_id=?", (b["device_id"],))
        sync_interfaces(self.conn, a["device_id"], [{"if_index": 1, "if_name": "eth0", "if_descr": "peer", "if_alias": "", "if_type": 6, "admin_status": 1, "oper_status": 2, "speed_bps": 1000, "counters": {}}])
        add_topology_link(self.conn, local_device_id=a["device_id"], local_if_index=1, remote_device_id=b["device_id"], remote_identifier="b", remote_port="eth0", evidence_type="ARP", confidence="inferred", evidence={})
        incident = next(x for x in correlate_recent(self.conn) if x["subject_device_id"] == b["device_id"])
        self.assertEqual(incident["confidence"], "low")
        self.assertIn("hypothesis", incident["ai_inference"].lower())

    def test_set_is_denied_by_global_gate(self):
        device = add_device(self.conn, {"display_name": "rw", "management_address": "10.2.0.1", "credential_reference": "v3", "write_enabled": True})
        with self.assertRaises(PermissionError):
            execute_set(self.conn, device_id=device["device_id"], oid="1.3.6.1.2.1.1.4.0", value_type="s", value="noc", config={"snmp_set_enabled": False}, resolver=self._profile())

    def test_set_is_denied_by_device_gate(self):
        device = add_device(self.conn, {"display_name": "ro", "management_address": "10.2.0.2", "credential_reference": "v3", "write_enabled": False})
        with self.assertRaises(PermissionError):
            execute_set(self.conn, device_id=device["device_id"], oid="1.3.6.1.2.1.1.4.0", value_type="s", value="noc", config={"snmp_set_enabled": True}, resolver=self._profile())

    def test_set_executes_only_after_both_gates_without_secret_argv(self):
        device = add_device(self.conn, {"display_name": "rw", "management_address": "10.2.0.3", "credential_reference": "v3", "write_enabled": True})
        captured = {}
        def runner(argv, **kwargs):
            captured["argv"] = list(argv)
            captured["env"] = dict(kwargs["env"])
            conf = Path(captured["env"]["SNMPCONFPATH"]) / "snmp.conf"
            captured["conf_mode"] = conf.stat().st_mode & 0o777
            captured["conf"] = conf.read_text(encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="1.3.6.1.2.1.1.4.0 = noc\n", stderr="")
        result = execute_set(self.conn, device_id=device["device_id"], oid="1.3.6.1.2.1.1.4.0", value_type="s", value="noc", config={"snmp_set_enabled": True}, resolver=self._profile(), runner=runner)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(captured["argv"][0], "snmpset")
        self.assertNotIn("-A", captured["argv"])
        self.assertNotIn("-X", captured["argv"])
        self.assertNotIn("dummy-auth", captured["argv"])
        self.assertNotIn("dummy-priv", captured["argv"])
        self.assertEqual(captured["conf_mode"], 0o600)
        self.assertIn("defSecurityLevel authPriv", captured["conf"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
