import unittest
from pathlib import Path
from server.edge1_automation_inventory_exporter import status_projection, SAFE_STATUS_KEYS, SAFE_SUMMARY_KEYS

class AutomationDetailUITests(unittest.TestCase):
    def test_projection_is_scalar_whitelist(self):
        for service in ['edge1-outstanding-actions.service','edge1-automation-watchdog.service','edge1-catalog-consistency.service']:
            p=status_projection(service)
            self.assertIsNotNone(p)
            if p.get('available'):
                self.assertTrue(set(p)-{'slug','available','status_url','summary',*SAFE_STATUS_KEYS} == set())
                for v in p.get('summary',{}).values(): self.assertTrue(v is None or isinstance(v,(bool,int,float,str)))
                self.assertTrue(set(p.get('summary',{})) <= SAFE_SUMMARY_KEYS)
    def test_ui_does_not_render_findings_or_payload_arrays(self):
        root=Path(__file__).resolve().parents[1]
        js=(root/'src/web/automation-center/app.js').read_text()
        self.assertNotIn('.findings',js)
        self.assertNotIn('payload_json',js)
        self.assertIn('bot_status',js)
        self.assertIn('Status JSON',js)
    def test_known_status_aliases_resolve_authenticated_paths(self):
        p=status_projection('edge1-catalog-consistency.service')
        self.assertEqual(p['status_url'],'/edge1-ops/status/catalog-consistency/status.json')
        self.assertNotIn('token',str(p).lower())
        self.assertNotIn('password',str(p).lower())
if __name__=='__main__': unittest.main()
