import sqlite3, tempfile, unittest
from pathlib import Path
from tools.unified_contacts.maintenance_bot import open_state, run

class MaintenanceBotTests(unittest.TestCase):
 def test_findings_and_enrichment_are_idempotent(self):
  with tempfile.TemporaryDirectory() as d:
   src=sqlite3.connect(':memory:'); src.row_factory=sqlite3.Row
   src.executescript('''
   CREATE TABLE contact_entities(id INTEGER PRIMARY KEY,entity_type TEXT,canonical_name TEXT,lifecycle_status TEXT);
   CREATE TABLE contact_points(id INTEGER PRIMARY KEY,point_type TEXT,normalized_value TEXT,lifecycle_status TEXT);
   CREATE TABLE contact_assertions(id INTEGER PRIMARY KEY,entity_id INTEGER,contact_point_id INTEGER);
   INSERT INTO contact_entities VALUES(1,'person','Jane Smith','active');
   INSERT INTO contact_entities VALUES(2,'person','Jane  Smith','active');
   INSERT INTO contact_points VALUES(1,'email','bad-email','active');
   INSERT INTO contact_assertions VALUES(1,1,1);
   ''')
   dst=open_state(Path(d)/'state.sqlite')
   a=run(src,dst); dst.commit(); b=run(src,dst); dst.commit()
   self.assertGreaterEqual(a['open_findings'],2)
   self.assertEqual(a['open_findings'],b['open_findings'])
   self.assertEqual(dst.execute("SELECT COUNT(*) FROM maintenance_findings WHERE finding_type='duplicate_entity'").fetchone()[0],1)
   self.assertGreater(dst.execute("SELECT COUNT(*) FROM enrichment_queue").fetchone()[0],0)
   dst.close(); src.close()
if __name__=='__main__': unittest.main()
