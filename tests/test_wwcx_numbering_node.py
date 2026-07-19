#!/usr/bin/env python3
import csv
import tempfile
import unittest
from pathlib import Path

from server.wwcx_numbering_node import import_rows, init_db, lookup, normalize_nanp


class NumberingNodeTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_nanp("+1 (212) 555-0100"), "2125550100")
        with self.assertRaises(ValueError):
            normalize_nanp("123")

    def test_import_and_lookup(self):
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
            self.assertEqual(import_rows(db, "fixture", rows), 1)
            result = lookup(db, "2125550100")
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["npa"], "212")
            self.assertEqual(result["assignments"][0]["company"], "Example Carrier")

    def test_reject_invalid_prefix_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "numbering.sqlite3"
            init_db(db)
            self.assertEqual(import_rows(db, "fixture", [{"NPA": "012", "NXX": "555"}]), 0)


if __name__ == "__main__":
    unittest.main()
