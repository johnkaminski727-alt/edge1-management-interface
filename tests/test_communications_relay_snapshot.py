from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

MODULE_PATH = SERVER / "communications_relay_snapshot.py"
spec = importlib.util.spec_from_file_location("communications_relay_snapshot", MODULE_PATH)
assert spec and spec.loader
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


def create_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                group_name TEXT NOT NULL,
                message_id TEXT,
                author TEXT,
                account TEXT,
                subject TEXT,
                date_rfc5322 TEXT,
                references_text TEXT,
                headers_json TEXT,
                body TEXT,
                created_at_utc TEXT NOT NULL
            );
            CREATE TABLE ingest_items (
                source_name TEXT NOT NULL,
                source_item_id TEXT NOT NULL,
                article_id INTEGER NOT NULL,
                detail_json TEXT,
                created_at_utc TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            """
            INSERT INTO articles (
                id, group_name, message_id, author, subject, body, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "wwcx.projects.edge1",
                    "<one@edge1.ww.cx>",
                    "Alice Example <alice@example.test>",
                    "Internal repository update",
                    "SECRET RAW BODY ONE",
                    "2026-08-18T06:00:00Z",
                ),
                (
                    2,
                    "usenet.comp.lang.python",
                    "<two@example.test>",
                    "Bob Example <bob@example.test>",
                    "External article subject",
                    "SECRET RAW BODY TWO",
                    "2026-08-18T06:01:00Z",
                ),
            ],
        )
        connection.executemany(
            """
            INSERT INTO ingest_items (
                source_name, source_item_id, article_id, detail_json, created_at_utc
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("edge1-repository", "commit:abc", 1, "{}", "2026-08-18T06:00:00Z"),
                ("eternal.comp.lang.python", "article:xyz", 2, "{}", "2026-08-18T06:01:00Z"),
            ],
        )
        connection.commit()


class RelaySnapshotTests(unittest.TestCase):
    def test_build_events_preserves_native_authority_without_body_or_raw_author(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "comms.sqlite3"
            create_database(database)

            events = relay.build_events(database)

            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["direction"], "internal")
            self.assertEqual(events[1]["direction"], "inbound")
            self.assertEqual(events[0]["native_record"]["source"], "edge1-comms-relay")
            self.assertEqual(events[0]["native_record"]["record_id"], "article:1")
            self.assertTrue(events[0]["provenance"]["authoritative_native_record"])
            self.assertFalse(events[0]["security"]["quarantine_release_authorized"])

            encoded = json.dumps(events, sort_keys=True)
            self.assertNotIn("SECRET RAW BODY", encoded)
            self.assertNotIn("Alice Example", encoded)
            self.assertNotIn("alice@example.test", encoded)
            self.assertIn("identity:nntp-author-sha256:", encoded)

    def test_unknown_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "comms.sqlite3"
            create_database(database)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE ingest_items SET source_name='unreviewed-source' WHERE article_id=1"
                )
                connection.commit()

            with self.assertRaises(relay.RelaySnapshotError):
                relay.build_events(database)

    def test_missing_ingest_link_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "comms.sqlite3"
            create_database(database)
            with sqlite3.connect(database) as connection:
                connection.execute("DELETE FROM ingest_items WHERE article_id=2")
                connection.commit()

            with self.assertRaises(relay.RelaySnapshotError):
                relay.build_events(database)

    def test_atomic_snapshot_contains_validated_metadata_only_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "comms.sqlite3"
            output = root / "events.jsonl"
            create_database(database)

            count = relay.write_snapshot_atomic(relay.build_events(database), output)

            self.assertEqual(count, 2)
            lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(output.stat().st_mode & 0o777, 0o640)
            self.assertNotIn("body", lines[0])
            self.assertEqual(lines[1]["channel"], "nntp")


if __name__ == "__main__":
    unittest.main()
