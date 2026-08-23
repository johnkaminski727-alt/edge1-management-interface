import sqlite3
import tempfile
from pathlib import Path
import unittest

from server.ava_office_manager import OfficeManagerStore
from server.number_portability_center import PortabilityStore


ROOT = Path(__file__).resolve().parents[1]


class SQLiteReadOnlyCompatibilityTests(unittest.TestCase):
    def test_ava_store_uses_delete_journal_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ava.sqlite3"
            OfficeManagerStore(path)
            with sqlite3.connect(path) as conn:
                mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            self.assertEqual(mode, "delete")
            self.assertFalse(Path(str(path) + "-wal").exists())
            self.assertFalse(Path(str(path) + "-shm").exists())

    def test_portability_store_uses_delete_journal_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portability.sqlite3"
            PortabilityStore(path)
            with sqlite3.connect(path) as conn:
                mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            self.assertEqual(mode, "delete")
            self.assertFalse(Path(str(path) + "-wal").exists())
            self.assertFalse(Path(str(path) + "-shm").exists())

    def test_guarded_live_repair_preserves_read_only_boundaries(self):
        script = (ROOT / "deploy/repair-office-portability-readonly-sqlite.sh").read_text(encoding="utf-8")
        self.assertIn("PRAGMA wal_checkpoint(TRUNCATE)", script)
        self.assertIn("PRAGMA journal_mode=DELETE", script)
        self.assertIn("PRAGMA integrity_check", script)
        self.assertIn("systemctl stop \"$AVA_SERVICE\" \"$PORT_SERVICE\"", script)
        self.assertIn("systemctl start \"$AVA_SERVICE\" \"$PORT_SERVICE\"", script)
        self.assertIn("/api/ava-office/summary", script)
        self.assertIn("/api/portability/summary", script)
        self.assertIn("activate-office-portability-operations-bridge.sh", script)
        self.assertIn("submission_authorized') is False", script)
        self.assertIn("cutover_authorized') is False", script)
        self.assertIn("main or a detached exact-commit checkout", script)
        self.assertIn("git -c safe.directory=\"$ROOT\"", script)
        for forbidden in (
            "asterisk -rx",
            "fwconsole",
            "carrier.submit",
            "telephony.route",
            "emergency.call",
        ):
            self.assertNotIn(forbidden, script.lower())


if __name__ == "__main__":
    unittest.main()
