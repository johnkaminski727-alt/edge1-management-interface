import importlib.util
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

auto=load('auto_inventory','server/edge1_automation_inventory_exporter.py')
api=load('api_inventory','server/edge1_api_directory_exporter.py')

class AutomationApiCenterTests(unittest.TestCase):
    def test_action_classification_is_conservative(self):
        self.assertEqual(auto.classify('edge1-contacts-maintenance.service','maintenance'),'AUTO-FIX')
        self.assertEqual(auto.classify('edge1-mail-contact-intake.service','contact intake'),'AUTO-STAGE')
        self.assertEqual(auto.classify('edge1-core-observation.service','read-only observation'),'READ-ONLY')
        self.assertEqual(auto.classify('edge1-mystery.service','does something'),'REVIEW-REQUIRED')
    def test_endpoint_regex_and_secret_path_guard(self):
        text='x="/api/example/status"; y="/mcp"; z="/not-api"'
        self.assertIn('/api/example/status',api.PATH_RE.findall(text))
        self.assertIn('/mcp',api.PATH_RE.findall(text))
        self.assertNotIn('/not-api',api.PATH_RE.findall(text))
    def test_navigation_keeps_contacts_and_ava_first(self):
        data=json.loads((ROOT/'config/edge1_operator/navigation_registry.json').read_text())
        mods=sorted(data['modules'],key=lambda m:(m['sort_order'],m['section'],m['label']))
        self.assertEqual([m['id'] for m in mods[:2]],['contacts-relationships','ava-agent'])
        ids={m['id'] for m in mods}; self.assertIn('automation-center',ids); self.assertIn('api-directory',ids)

    def test_synthetic_status_covers_custom_timer_without_feed(self):
        item={
            "timer":"edge1-example.timer", "service":"edge1-example.service",
            "custom":True, "enabled":"enabled", "state":"active",
            "service_state":"inactive", "last_result":"success", "next_run":"soon",
        }
        result=auto.synthetic_status(item)
        self.assertTrue(result["available"])
        self.assertTrue(result["synthetic"])
        self.assertEqual(result["state"],"healthy")
        self.assertEqual(result["slug"],"edge1-example")

    def test_ui_assets_use_operator_shell_and_inventory(self):
        for page,module in [('automation-center','automation-center'),('api-directory','api-directory')]:
            html=(ROOT/f'src/web/{page}/index.html').read_text()
            js=(ROOT/f'src/web/{page}/app.js').read_text()
            self.assertIn('operator-shell/shell.js',html); self.assertIn(f'data-module="{module}"',html); self.assertIn('inventory.json',js)

if __name__=='__main__': unittest.main()
