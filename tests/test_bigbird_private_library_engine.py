#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "services/bigbird-ai-gateway/app/library_engine.py"
BOOTSTRAP = ROOT / "tools/private_library/bootstrap_library_runtime.py"

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

class BigBirdPrivateLibraryEngineTests(unittest.TestCase):
    def test_bootstrap_and_live_search_contract(self):
        engine = load(ENGINE, "edge1_library_engine")
        bootstrap = load(BOOTSTRAP, "edge1_library_bootstrap")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "library.sqlite3"
            bootstrap.create_or_validate(db, True)
            results = engine.search_library(db, "VPN", ["operations"], limit=3, excerpt_chars=200)
            self.assertTrue(results)
            item = results[0]
            self.assertEqual(item.collection, "operations")
            self.assertEqual(item.chunk_index, 0)
            self.assertIn("VPN", item.excerpt)
            self.assertEqual(item.source_path, "operations/private-library-runtime-bootstrap.md")
            con = sqlite3.connect(db)
            try:
                self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                con.close()

    def test_secret_guard_and_collection_filter(self):
        engine = load(ENGINE, "edge1_library_engine_secret")
        bootstrap = load(BOOTSTRAP, "edge1_library_bootstrap_secret")
        self.assertTrue(engine.contains_secret("password=example"))
        self.assertTrue(engine.contains_secret("-----BEGIN PRIVATE KEY-----"))
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "library.sqlite3"
            bootstrap.create_or_validate(db, True)
            self.assertEqual(engine.search_library(db, "VPN", ["not-operations"]), [])

if __name__ == "__main__":
    unittest.main()
