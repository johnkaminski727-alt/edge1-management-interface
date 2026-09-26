#!/usr/bin/env python3
"""Offline checks for read-only backup status API."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "server" / "backup_recovery_server.py"
spec = importlib.util.spec_from_file_location("edge1_backup_recovery_server", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class StatusTests(unittest.TestCase):
    def test_empty_directory_makes_no_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mod.load_status(Path(tmp))
            self.assertEqual(result["records"], [])
            self.assertIsNone(result["last_backup"])
            self.assertTrue(result["read_only"])

    def test_status_manifest_whitelists_fields(self):
        record = mod.sanitized_record({
            "archive":"edge1-20260926T030139Z.tar.gz.gpg",
            "created_at":"2026-09-26T03:01:39Z",
            "size_bytes":13063,
            "upload":"uploaded",
            "integrity":"unknown",
            "restore_test":"unknown",
            "secret":"NEVER RETURN",
            "dropbox_token":"NEVER RETURN",
        })
        self.assertEqual(record["upload"],"uploaded")
        self.assertNotIn("secret",record)
        self.assertNotIn("dropbox_token",record)
        self.assertEqual(record["restore_test"],"unknown")

    def test_bad_archive_name_rejected(self):
        self.assertIsNone(mod.sanitized_record({"archive":"../../secrets.tar.gz.gpg","created_at":"2026-09-26T03:01:39Z"}))

    def test_untrusted_state_downgraded(self):
        record=mod.sanitized_record({"archive":"x.tar.gz.gpg","created_at":"2026-09-26T03:01:39Z","upload":"guaranteed","integrity":"verified"})
        self.assertEqual(record["upload"],"unknown")

    def test_malformed_file_ignored_and_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            (path/"invalid.json").write_text("{oops")
            for i in [1,3,2]:
                (path/f"{i}.json").write_text(json.dumps({"archive":f"edge1-{i}.tar.gz.gpg","created_at":f"2026-09-26T0{i}:00:00Z","upload":"uploaded"}))
            result=mod.load_status(path)
            self.assertEqual(len(result["records"]),3)
            self.assertEqual(result["records"][0]["archive"],"edge1-3.tar.gz.gpg")

if __name__=="__main__":
    unittest.main()
