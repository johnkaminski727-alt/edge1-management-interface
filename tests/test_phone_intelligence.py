from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from server.phone_intelligence import (
    PhoneIntelligenceError,
    PhoneIntelligenceStore,
    parse_phone_api_path,
)


SCHEMA = """
CREATE TABLE phone_numbers (
    id INTEGER PRIMARY KEY,
    normalized_number TEXT UNIQUE,
    display_number TEXT,
    country_code TEXT,
    national_number TEXT,
    npa TEXT,
    status TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    occurrence_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE organizations (
    id INTEGER PRIMARY KEY,
    name TEXT,
    organization_type TEXT,
    city TEXT,
    region TEXT,
    country TEXT,
    website TEXT,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE associations (
    id INTEGER PRIMARY KEY,
    phone_number_id INTEGER,
    organization_id INTEGER,
    association_label TEXT,
    confidence TEXT,
    research_notes TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE source_documents (
    id INTEGER PRIMARY KEY,
    document_type TEXT,
    source_name TEXT,
    source_reference TEXT,
    statement_date TEXT,
    account_reference TEXT,
    sha256 TEXT,
    verification_status TEXT,
    notes TEXT,
    created_at TEXT
);

CREATE TABLE occurrences (
    id INTEGER PRIMARY KEY,
    phone_number_id INTEGER,
    source_document_id INTEGER,
    occurred_at TEXT,
    occurrence_type TEXT,
    direction TEXT,
    raw_value TEXT,
    notes TEXT,
    created_at TEXT
);

CREATE TABLE evidence (
    id INTEGER PRIMARY KEY,
    association_id INTEGER,
    evidence_type TEXT,
    source_title TEXT,
    source_url TEXT,
    source_reference TEXT,
    evidence_summary TEXT,
    verification_status TEXT,
    retrieved_at TEXT,
    created_at TEXT
);
"""


class PhoneIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "phones.sqlite"

        conn = sqlite3.connect(self.db)
        conn.executescript(SCHEMA)

        conn.execute(
            """
            INSERT INTO phone_numbers
            VALUES(
                1, '+13065932201', '(306) 593-2201',
                '1', '3065932201', '306', 'confirmed',
                NULL, NULL, 12, 'now', 'now'
            )
            """
        )

        conn.execute(
            """
            INSERT INTO organizations
            VALUES(
                1, 'Example Store', 'Retail',
                NULL, 'Canora, SK', 'Canada',
                'https://example.invalid',
                NULL, 'now', 'now'
            )
            """
        )

        conn.execute(
            """
            INSERT INTO associations
            VALUES(
                1, 1, 1, 'Example Store',
                'confirmed', 'Verified public listing',
                'now', 'now'
            )
            """
        )

        conn.execute(
            """
            INSERT INTO source_documents
            VALUES(
                1, 'telus-bill', 'bill.pdf', 'bill.pdf',
                NULL, NULL, NULL, 'missing',
                'fixture', 'now'
            )
            """
        )

        conn.execute(
            """
            INSERT INTO occurrences
            VALUES(
                1, 1, 1, NULL, 'bill-reference',
                NULL, '(306) 593-2201',
                'fixture', 'now'
            )
            """
        )

        conn.execute(
            """
            INSERT INTO evidence
            VALUES(
                1, 1, 'public-research',
                'Public listing',
                'https://example.invalid',
                NULL, 'Confirmed',
                'verified', NULL, 'now'
            )
            """
        )

        conn.commit()
        conn.close()

        self.store = PhoneIntelligenceStore(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dashboard(self):
        data = self.store.dashboard()

        self.assertEqual(data["total_numbers"], 1)
        self.assertEqual(data["aggregate_occurrences"], 12)
        self.assertEqual(data["source_documents"], 1)
        self.assertEqual(data["bill_relationships"], 1)
        self.assertEqual(data["statuses"]["confirmed"], 1)

    def test_list_search(self):
        data = self.store.list_phones(
            query="Example",
            status="confirmed",
        )

        self.assertEqual(data["total"], 1)
        self.assertEqual(
            data["phones"][0]["normalized_number"],
            "+13065932201",
        )

    def test_numeric_search(self):
        data = self.store.list_phones(
            query="3065932201"
        )

        self.assertEqual(data["total"], 1)

    def test_detail(self):
        data = self.store.phone_detail(1)

        self.assertEqual(
            data["association_label"],
            "Example Store",
        )

        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(len(data["evidence"]), 1)

    def test_missing_detail(self):
        self.assertIsNone(
            self.store.phone_detail(999)
        )

    def test_invalid_status(self):
        with self.assertRaises(
            PhoneIntelligenceError
        ):
            self.store.list_phones(
                status="definitely-not-valid"
            )

    def test_query_only_connection(self):
        with closing(self.store.connect()) as conn:
            with self.assertRaises(
                sqlite3.OperationalError
            ):
                conn.execute(
                    """
                    INSERT INTO phone_numbers(
                        normalized_number
                    ) VALUES('+15555550100')
                    """
                )

    def test_route_parser(self):
        route = parse_phone_api_path(
            "/v1/intelligence/phones"
            "?status=confirmed&limit=25"
        )

        self.assertEqual(route[0], "phones")
        self.assertEqual(
            route[1]["status"],
            "confirmed",
        )
        self.assertEqual(
            route[1]["limit"],
            "25",
        )

        self.assertEqual(
            parse_phone_api_path(
                "/v1/intelligence/dashboard"
            ),
            ("dashboard", {}),
        )

        self.assertEqual(
            parse_phone_api_path(
                "/v1/intelligence/phones/12"
            ),
            ("phone", {"phone_id": "12"}),
        )

        self.assertIsNone(
            parse_phone_api_path("/something-else")
        )


if __name__ == "__main__":
    unittest.main()
