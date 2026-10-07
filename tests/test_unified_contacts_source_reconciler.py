import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.unified_contacts.source_reconciler import reconcile


SCHEMA = '''
CREATE TABLE source_documents(
 id INTEGER PRIMARY KEY,
 sha256 TEXT
);
CREATE TABLE provenance_records(
 id INTEGER PRIMARY KEY,
 source_document_id INTEGER,
 source_kind TEXT,
 source_name TEXT,
 source_reference TEXT,
 source_url TEXT,
 source_sha256 TEXT,
 verification_status TEXT
);
'''


class SourceReconcilerTests(unittest.TestCase):
    def database(self):
        con = sqlite3.connect(':memory:')
        con.row_factory = sqlite3.Row
        con.executescript(SCHEMA)
        return con

    def test_hash_match_is_verified_and_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'statement.pdf'
            source.write_bytes(b'authoritative evidence')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            con = self.database()
            con.execute('INSERT INTO source_documents(id,sha256) VALUES(1,?)', (digest,))
            con.execute('''INSERT INTO provenance_records
                (id,source_document_id,source_kind,source_name,source_reference,verification_status)
                VALUES(1,1,'document','statement.pdf','old/statement.pdf','missing_source')''')
            result = reconcile(con, [root], '2026-10-07T10:00:00+00:00', apply=True)
            self.assertEqual(result['verified'], 1)
            row = con.execute('SELECT * FROM provenance_source_locations WHERE provenance_id=1').fetchone()
            self.assertEqual(row['verification_status'], 'verified')
            self.assertEqual(row['match_method'], 'sha256')
            self.assertEqual(Path(row['location']), source)
            con.close()

    def test_unique_filename_without_hash_is_only_staged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'invoice.pdf'
            source.write_bytes(b'no retained hash')
            con = self.database()
            con.execute('''INSERT INTO provenance_records
                (id,source_kind,source_name,source_reference,verification_status)
                VALUES(2,'document','invoice.pdf','invoice.pdf','missing_source')''')
            result = reconcile(con, [root], '2026-10-07T10:00:00+00:00', apply=True)
            self.assertEqual(result['candidates'], 1)
            row = con.execute('SELECT * FROM provenance_source_locations WHERE provenance_id=2').fetchone()
            self.assertIsNone(row)
            con.close()

    def test_multiple_filename_matches_require_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a').mkdir()
            (root / 'b').mkdir()
            (root / 'a' / 'invoice.pdf').write_bytes(b'a')
            (root / 'b' / 'invoice.pdf').write_bytes(b'b')
            con = self.database()
            con.execute('''INSERT INTO provenance_records
                (id,source_kind,source_name,source_reference,verification_status)
                VALUES(3,'document','invoice.pdf','invoice.pdf','missing_source')''')
            result = reconcile(con, [root], '2026-10-07T10:00:00+00:00', apply=False)
            self.assertEqual(result['ambiguous'], 1)
            self.assertEqual(result['results'][0]['action_level'], 'REVIEW_REQUIRED')
            con.close()


if __name__ == '__main__':
    unittest.main()
