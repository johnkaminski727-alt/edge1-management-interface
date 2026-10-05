from contextlib import closing
#!/usr/bin/env python3
"""Regression tests for AVA's natural-language Private Library retrieval."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from test_bigbird_private_library_engine import load, ENGINE, BOOTSTRAP

class AvaLibraryRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.engine = load(ENGINE, "ava_retrieval_engine")
        bootstrap = load(BOOTSTRAP, "ava_retrieval_bootstrap")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "library.sqlite3"
        bootstrap.create_or_validate(self.db, False)
        with closing(sqlite3.connect(self.db)) as c, c:
            for ident, collection, text in [
                ("vpn", "operations", "VPN restoration checkpoint instructions."),
                ("unsafe", "operations", "VPN password=" + "never-expose"),
                ("private", "excluded", "VPN restoration secret collection."),
                ("long", "operations", "Preamble. " * 200 + "Target needle evidence near the end.")]:
                c.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                          (ident, collection, ident, ident + ".md", "internal", "2026-10-05"))
                c.execute("INSERT INTO chunks(document_id,chunk_index,locator,text) VALUES (?,0,'section',?)",
                          (ident, text))

    def search(self, query, **kwargs):
        return self.engine.search_library(self.db, query, ["operations"], **kwargs)

    def test_natural_question_and_partial_match(self):
        self.assertEqual(self.search("How do I restore the VPN?")[0].document_id, "vpn")

    def test_collections_and_secret_results_stay_excluded(self):
        rows = self.search("VPN")
        self.assertEqual([row.document_id for row in rows], ["vpn"])
        self.assertEqual(self.search("password=" + "provided"), [])

    def test_nonempty_stopword_query_does_not_browse(self):
        self.assertEqual(self.search("how do I"), [])
        self.assertEqual(self.search("unfindable"), [])

    def test_excerpt_contains_query_evidence_and_is_bounded(self):
        row = self.search("needle", excerpt_chars=120)[0]
        self.assertIn("needle", row.excerpt)
        self.assertLessEqual(len(row.excerpt), 120)
        self.assertEqual(row.locator, "section")

    def test_search_does_not_mutate_database(self):
        before = self.db.read_bytes()
        self.search("VPN")
        self.assertEqual(self.db.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
