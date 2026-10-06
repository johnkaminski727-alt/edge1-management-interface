import json, sqlite3, tempfile, unittest
from pathlib import Path
from server.edge1_navigation_registry import migrate, import_registry, export_registry, set_enabled, set_theme

FIXTURE=Path(__file__).resolve().parents[1]/'config/edge1_operator/navigation_registry.json'
class T(unittest.TestCase):
    def test_import_export_switch_and_theme(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'nav.sqlite3'
            with sqlite3.connect(db) as c:
                c.row_factory=sqlite3.Row; import_registry(c,json.loads(FIXTURE.read_text()),replace=True)
                original=len(export_registry(c)['modules'])
                set_enabled(c,'mail-room',False)
                self.assertEqual(len(export_registry(c)['modules']),original-1)
                allmods=export_registry(c,include_disabled=True)['modules']
                mail=next(x for x in allmods if x['id']=='mail-room')
                self.assertFalse(mail['enabled'])
                set_enabled(c,'mail-room',True); set_theme(c,'mail-room','dark')
                mail=next(x for x in export_registry(c)['modules'] if x['id']=='mail-room')
                self.assertEqual(mail['theme'],'dark')
    def test_safety_is_fail_closed(self):
        data=json.loads(FIXTURE.read_text()); data['safety']['mutations_enabled']=True
        with tempfile.TemporaryDirectory() as d:
            c=sqlite3.connect(Path(d)/'n.db'); c.row_factory=sqlite3.Row
            with self.assertRaises(ValueError): import_registry(c,data,replace=True)
