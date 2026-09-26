#!/usr/bin/env python3
"""Offline tests for upload-only rclone metadata importer."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"tools"/"backup"/"import_rclone_listing.py"
spec=importlib.util.spec_from_file_location("import_rclone_listing",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def item(path, size=13063, is_dir=False):
    return {"Path":path,"Size":size,"IsDir":is_dir,"ModTime":"2026-09-26T03:01:43Z"}

class ImportTests(unittest.TestCase):
    def test_only_exact_encrypted_edge1_daily_archives(self):
        rows=mod.parse_listing([
            item("Edge1-Recovery/daily/edge1-20260926T030139Z.tar.gz.gpg"),
            item("Edge1-Recovery/daily/edge1-20260926T011627Z.tar.gz.gpg"),
            item("Edge1-Recovery/edge1-recovery-v2.tar.gz.gpg"),
            item("unrelated/edge1-20260926T030139Z.tar.gz.gpg"),
            item("edge1-20260926T030139Z.tar.gz.gpg", is_dir=True),
            item("edge1-20260926T030139Z.tar.gz.gpg/../secrets"),
        ])
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["created_at"],"2026-09-26T03:01:39Z")
        self.assertTrue(all(row["integrity"]=="unknown" and row["restore_test"]=="unknown" for row in rows))

    def test_invalid_listing_fails_closed(self):
        with self.assertRaises(ValueError):
            mod.parse_listing({"Path":"edge1-20260926T030139Z.tar.gz.gpg"})
        self.assertEqual(mod.parse_listing([item("edge1-20260926T030139Z.tar.gz.gpg",size=-1)]),[])

    def test_atomic_write_preserves_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)
            rows=mod.parse_listing([item("edge1-20260926T030139Z.tar.gz.gpg")])
            mod.write_manifests(rows,dest)
            file=dest/(rows[0]["archive"]+".json")
            self.assertEqual(json.loads(file.read_text())["upload"],"uploaded")
            old={"archive":rows[0]["archive"],"restore_test":"verified"}
            file.write_text(json.dumps(old))
            mod.write_manifests(rows,dest)
            self.assertEqual(json.loads(file.read_text())["restore_test"],"verified")

    def test_no_untrusted_fields_escape(self):
        row=item("edge1-20260926T030139Z.tar.gz.gpg")
        row["DropboxToken"]="DO-NOT-PUBLISH"
        self.assertNotIn("DropboxToken",mod.parse_listing([row])[0])

if __name__=="__main__": unittest.main()
