import sqlite3
import unittest
from tools.unified_contacts import schema_openpgp as schema
class TestOpenPGPSchema(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('CREATE TABLE contact_points(id INTEGER PRIMARY KEY)')
        self.db.execute('INSERT INTO contact_points VALUES(1)')
        schema.apply_schema(self.db)
    def test_private_key_material_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO contact_openpgp_keys(contact_point_id,fingerprint,public_key_armored) VALUES(1,?,?)",('A'*40,'-----BEGIN PGP PRIVATE KEY BLOCK-----'))
    def test_require_encryption_policy_allowed(self):
        self.db.execute("INSERT INTO contact_openpgp_policy(contact_point_id,mode) VALUES(1,'require_encryption')")
        self.assertEqual(self.db.execute('SELECT mode FROM contact_openpgp_policy').fetchone()[0],'require_encryption')
if __name__ == '__main__': unittest.main()
