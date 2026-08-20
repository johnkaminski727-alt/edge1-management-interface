#!/usr/bin/env python3
from __future__ import print_function

import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import edge1_snmp_server_pollers as pollers


class ServerPollerTests(unittest.TestCase):
    @staticmethod
    def fake_proc(root):
        with open(os.path.join(root, "loadavg"), "w") as handle:
            handle.write("0.10 0.20 0.30 1/100 123\n")
        with open(os.path.join(root, "uptime"), "w") as handle:
            handle.write("1234.50 1200.00\n")
        with open(os.path.join(root, "meminfo"), "w") as handle:
            handle.write("MemTotal:       1000 kB\nMemAvailable:    250 kB\n")
        os.mkdir(os.path.join(root, "1"))
        os.mkdir(os.path.join(root, "22"))

    def test_collect_is_bounded_and_host_native(self):
        with tempfile.TemporaryDirectory() as td:
            proc = os.path.join(td, "proc")
            disk = os.path.join(td, "disk")
            os.mkdir(proc)
            os.mkdir(disk)
            self.fake_proc(proc)
            snapshot = pollers.collect_snapshot("edge1", "Edge1 Server", "edge1.ww.cx", disk_path=disk, proc_root=proc)
            self.assertEqual(snapshot["schema"], pollers.SCHEMA)
            self.assertEqual(snapshot["source_type"], "host-native")
            self.assertEqual(snapshot["metrics"]["load_1m"], 0.10)
            self.assertEqual(snapshot["metrics"]["memory_used_percent"], 75.0)
            self.assertEqual(snapshot["metrics"]["process_count"], 2.0)
            serialized = json.dumps(snapshot).lower()
            self.assertNotIn("services", serialized)
            self.assertNotIn("interfaces", serialized)
            self.assertNotIn("credential", serialized)

    def test_server_pollers_never_create_snmp_devices(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "snmp.sqlite3")
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            conn.execute("CREATE TABLE devices(device_id TEXT PRIMARY KEY)")
            conn.execute("CREATE TABLE audit(audit_id TEXT,ts TEXT,actor TEXT,source TEXT,action TEXT,target TEXT,reason TEXT,before_json TEXT,after_json TEXT,result TEXT,correlation_id TEXT,ai_involvement TEXT,rollback_json TEXT)")
            pollers.ensure_schema(conn)
            snapshot = {
                "schema": pollers.SCHEMA,
                "generated_at": pollers.utcnow(),
                "poller_id": "edge1",
                "display_name": "Edge1 Server",
                "observer_host": "edge1.ww.cx",
                "source_type": "host-native",
                "metrics": {"load_1m": 0.1, "memory_used_percent": 20.0},
            }
            first = pollers.ingest_snapshot(conn, snapshot)
            second = pollers.ingest_snapshot(conn, snapshot)
            self.assertEqual(first["samples_inserted"], 2)
            self.assertEqual(second["samples_inserted"], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM devices").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM server_pollers").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM server_metrics").fetchone()[0], 2)
            conn.close()

    def test_jsonl_is_private_and_import_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "snmp.sqlite3")
            path = os.path.join(td, "measurements.jsonl")
            snapshot = {
                "schema": pollers.SCHEMA,
                "generated_at": pollers.utcnow(),
                "poller_id": "business159-shared-host",
                "display_name": "WW.CX Shared Host",
                "observer_host": "business159.web-hosting.com",
                "source_type": "host-native",
                "metrics": {"load_1m": 0.2, "disk_used_percent": 42.0},
            }
            pollers.append_jsonl(path, snapshot)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            conn = pollers.connect(db)
            first = pollers.ingest_jsonl(conn, path)
            second = pollers.ingest_jsonl(conn, path)
            self.assertEqual(first["samples_inserted"], 2)
            self.assertEqual(second["samples_inserted"], 0)
            self.assertEqual(pollers.health(conn)["server_pollers"], 1)
            conn.close()

    def test_unknown_or_out_of_range_metrics_fail_closed(self):
        base = {
            "schema": pollers.SCHEMA,
            "generated_at": pollers.utcnow(),
            "poller_id": "bad",
            "display_name": "Bad",
            "observer_host": "bad.example",
            "source_type": "host-native",
        }
        unknown = dict(base, metrics={"password": 1})
        with self.assertRaises(ValueError):
            pollers.validate_snapshot(unknown)
        over = dict(base, metrics={"memory_used_percent": 101})
        with self.assertRaises(ValueError):
            pollers.validate_snapshot(over)

    def test_deployment_assets_preserve_security_boundary(self):
        service = open(os.path.join(ROOT, "deploy", "edge1-snmp-poller.service"), "r").read()
        installer = open(os.path.join(ROOT, "deploy", "install-snmp-server-poller-shared-host.sh"), "r").read()
        source = open(os.path.join(ROOT, "server", "edge1_snmp_server_pollers.py"), "r").read()
        sync_service = open(os.path.join(ROOT, "deploy", "edge1-snmp-business159-sync.service"), "r").read()
        sync_script = open(os.path.join(ROOT, "deploy", "sync-business159-snmp-server-poller.sh"), "r").read()
        self.assertIn("edge1_snmp_server_pollers.py", service)
        self.assertIn("--poller-id edge1", service)
        self.assertIn("business159-measurements.jsonl", service)
        self.assertIn("edge1-snmp-business159-sync.service", service)
        self.assertIn("After=network-online.target edge1-snmp-business159-sync.service", service)
        self.assertIn("Wants=network-online.target edge1-snmp-business159-sync.service", service)
        self.assertIn("*/5 * * * *", installer)
        self.assertIn("business159.web-hosting.com", installer)
        self.assertIn('sh "$REPO_ROOT/deploy/snmp-server-poller-shared-host-smoke-test.sh"', installer)
        self.assertNotIn('\n"$REPO_ROOT/deploy/snmp-server-poller-shared-host-smoke-test.sh"\n', installer)
        self.assertIn("User=root", sync_service)
        self.assertIn("NoNewPrivileges=true", sync_service)
        self.assertIn("CapabilityBoundingSet=CAP_CHOWN", sync_service)
        self.assertIn("AmbientCapabilities=CAP_CHOWN", sync_service)
        self.assertNotIn("CAP_NET_ADMIN", sync_service)
        self.assertNotIn("CAP_SYS_ADMIN", sync_service)
        self.assertIn("ReadWritePaths=/var/lib/edge1-snmp/server-pollers", sync_service)
        self.assertIn("/usr/local/libexec/business159-tunnel/ssh", sync_script)
        self.assertIn("-o BatchMode=yes", sync_script)
        self.assertIn("-o StrictHostKeyChecking=yes", sync_script)
        self.assertIn("MAX_RECORDS=576", sync_script)
        self.assertIn("MAX_BYTES=2097152", sync_script)
        self.assertIn("module.validate_snapshot(payload)", sync_script)
        self.assertIn('payload.get("poller_id") != expected_poller', sync_script)
        self.assertIn('payload.get("observer_host") != expected_host', sync_script)
        self.assertIn('mv -f "$TMP" "$DEST"', sync_script)
        self.assertNotIn("IdentityFile", sync_script)
        self.assertNotIn("public_html", sync_script)
        for forbidden in ("socket", "snmpd", "snmptrapd", "udp:161", "subprocess", "urlopen"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ServerPollerTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("SNMP host-native server poller validation passed (%d tests)" % result.testsRun)
