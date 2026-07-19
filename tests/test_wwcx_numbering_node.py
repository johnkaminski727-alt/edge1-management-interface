#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from server.wwcx_numbering_node import (
    import_rows,
    init_db,
    list_sources,
    lookup,
    normalize_nanp,
    remove_source,
    validate_source,
)


class NumberingNodeTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_nanp("+1 (212) 555-0100"), "2125550100")
        with self.assertRaises(ValueError):
            normalize_nanp("123")

    def test_source_validation(self):
        self.assertEqual(validate_source("wwcx-controlled-test"), "wwcx-controlled-test")
        with self.assertRaises(ValueError):
            validate_source("bad source name")

    def test_import_lookup_provenance_and_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "numbering.sqlite3"
            init_db(db)
            rows = [
                {
                    "NPA": "212",
                    "NXX": "555",
                    "Country": "US",
                    "Region": "NY",
                    "Rate Center": "NEW YORK CITY",
                    "OCN": "9999",
                    "Company": "Example Carrier",
                    "Status": "AS",
                }
            ]
            result = import_rows(db, "fixture", rows, checksum="abc123")
            self.assertEqual(result["imported"], 1)
            self.assertEqual(result["rejected"], 0)

            lookup_result = lookup(db, "2125550100")
            self.assertIsNotNone(lookup_result)
            assert lookup_result is not None
            self.assertEqual(lookup_result["npa"], "212")
            self.assertEqual(
                lookup_result["assignments"][0]["company"], "Example Carrier"
            )

            sources = list_sources(db)
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["source"], "fixture")
            self.assertEqual(sources[0]["sha256"], "abc123")

            removed = remove_source(db, "fixture")
            self.assertEqual(removed["removed"], 1)
            self.assertIsNone(lookup(db, "2125550100"))
            self.assertEqual(list_sources(db), [])

    def test_reject_invalid_prefix_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "numbering.sqlite3"
            init_db(db)
            result = import_rows(db, "fixture", [{"NPA": "012", "NXX": "555"}])
            self.assertEqual(result["imported"], 0)
            self.assertEqual(result["rejected"], 1)

    def test_replace_source_is_atomic_for_valid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "numbering.sqlite3"
            init_db(db)
            import_rows(db, "fixture", [{"NPA": "212", "NXX": "555"}])
            result = import_rows(
                db,
                "fixture",
                [{"NPA": "646", "NXX": "555"}],
                replace_source=True,
            )
            self.assertEqual(result["imported"], 1)
            self.assertIsNone(lookup(db, "2125550100"))
            self.assertIsNotNone(lookup(db, "6465550100"))


if __name__ == "__main__":
    unittest.main()
