import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.unified_contacts.maintenance_bot import apply_safe_fixes, open_source, open_state, run


SCHEMA = '''
CREATE TABLE contact_entities(
 id INTEGER PRIMARY KEY, entity_type TEXT, canonical_name TEXT, display_name TEXT,
 lifecycle_status TEXT, verification_status TEXT, updated_at TEXT
);
CREATE TABLE contact_points(
 id INTEGER PRIMARY KEY, point_type TEXT, normalized_value TEXT, display_value TEXT,
 classification TEXT, lifecycle_status TEXT, updated_at TEXT
);
CREATE TABLE contact_assertions(id INTEGER PRIMARY KEY, entity_id INTEGER, contact_point_id INTEGER);
'''


class MaintenanceBotTests(unittest.TestCase):
    def test_findings_and_enrichment_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA + '''
                INSERT INTO contact_entities VALUES(1,'person','Jane Smith','Jane Smith','active','unverified',NULL);
                INSERT INTO contact_entities VALUES(2,'person','Jane  Smith','Jane Smith','active','unverified',NULL);
                INSERT INTO contact_points VALUES(1,'email','bad-email','bad-email',NULL,'active',NULL);
                INSERT INTO contact_assertions VALUES(1,1,1);
            ''')
            dst = open_state(Path(directory) / 'state.sqlite')
            first = run(src, dst)
            dst.commit()
            second = run(src, dst)
            dst.commit()
            self.assertGreaterEqual(first['open_findings'], 2)
            self.assertEqual(first['open_findings'], second['open_findings'])
            self.assertEqual(
                dst.execute("SELECT COUNT(*) FROM maintenance_findings WHERE finding_type='duplicate_entity'").fetchone()[0], 1
            )
            self.assertGreater(dst.execute("SELECT COUNT(*) FROM enrichment_queue").fetchone()[0], 0)
            self.assertGreater(dst.execute("SELECT COUNT(*) FROM candidate_changes").fetchone()[0], 0)
            src.close()
            dst.close()

    def test_safe_autofix_only_fills_missing_display_fields_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / 'contacts.sqlite'
            state_path = Path(directory) / 'state.sqlite'
            backup_dir = Path(directory) / 'backups'
            con = sqlite3.connect(source_path)
            con.executescript(SCHEMA + '''
                INSERT INTO contact_entities VALUES(1,'person','Jane Smith',NULL,'active','verified',NULL);
                INSERT INTO contact_entities VALUES(2,'person','Keep Name','Custom Display','active','verified',NULL);
                INSERT INTO contact_points VALUES(1,'email','jane@example.com',NULL,NULL,'active',NULL);
                INSERT INTO contact_points VALUES(2,'phone','+13065550100','(306) 555-0100',NULL,'active',NULL);
            ''')
            con.commit()
            con.close()

            dst = open_state(state_path)
            src = open_source(source_path, writable=True)
            first = apply_safe_fixes(src, source_path, dst, 1, backup_dir)
            dst.commit()
            self.assertEqual(first['planned'], 2)
            self.assertEqual(first['applied'], 2)
            self.assertTrue(Path(first['backup']).is_file())
            self.assertEqual(src.execute('SELECT display_name FROM contact_entities WHERE id=1').fetchone()[0], 'Jane Smith')
            self.assertEqual(src.execute('SELECT display_name FROM contact_entities WHERE id=2').fetchone()[0], 'Custom Display')
            self.assertEqual(src.execute('SELECT display_value FROM contact_points WHERE id=1').fetchone()[0], 'jane@example.com')
            self.assertEqual(src.execute('SELECT display_value FROM contact_points WHERE id=2').fetchone()[0], '(306) 555-0100')
            second = apply_safe_fixes(src, source_path, dst, 2, backup_dir)
            self.assertEqual(second['planned'], 0)
            self.assertEqual(second['applied'], 0)
            self.assertEqual(dst.execute("SELECT COUNT(*) FROM remediation_actions WHERE action_level='AUTO_FIX'").fetchone()[0], 2)
            src.close()
            dst.close()


if __name__ == '__main__':
    unittest.main()
