import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

class RecoveryRehearsalTests(unittest.TestCase):
    def test_rehearse_one_restores_disposable_sqlite(self):
        mod=load('recovery_rehearsal','tools/automation/recovery_rehearsal_bot.py')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'source.sqlite'; work=root/'work'; work.mkdir()
            with sqlite3.connect(src) as db:
                db.execute('create table evidence(id integer primary key, value text)')
                db.execute("insert into evidence(value) values ('example')")
            row=mod.rehearse_one('fixture',src,work)
            self.assertEqual(row['state'],'passed')
            self.assertTrue(row['integrity_ok'])
            self.assertTrue(row['schema_parity'])
            self.assertFalse(row['production_modified'])

    def test_rehearsal_has_no_secret_or_production_restore_contract(self):
        text=(ROOT/'tools/automation/recovery_rehearsal_bot.py').read_text()
        self.assertIn("'production_restore_performed': False",text)
        self.assertIn("'secrets_exposed': False",text)
        self.assertNotIn('password=',text.lower())

    def test_backup_verification_requires_general_rehearsal(self):
        text=(ROOT/'tools/automation/backup_verification_bot.py').read_text()
        self.assertIn('general_ok',text)
        self.assertIn("'general_restore_rehearsal'",text)
        self.assertIn("wwcx.backup-verification.v2",text)

if __name__=='__main__': unittest.main()
