import json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from tools.automation.action_lifecycle_bot import run as lifecycle_run
from tools.automation.api_surface_health_bot import build as api_build

class Wave6Tests(unittest.TestCase):
    def test_action_lifecycle_tracks_resolution_without_production_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source=root/'actions.json'; state=root/'state.sqlite3'
            source.write_text(json.dumps({'actions':[{'id':'a','source':'mail','priority':'high','title':'A'}]}))
            first=lifecycle_run(source=source,state=state,now=datetime(2026,10,7,12,tzinfo=timezone.utc))
            self.assertEqual(first['summary']['new'],1); self.assertFalse(first['production_mutation_performed'])
            source.write_text(json.dumps({'actions':[]}))
            second=lifecycle_run(source=source,state=state,now=datetime(2026,10,7,13,tzinfo=timezone.utc))
            self.assertEqual(second['summary']['resolved_this_run'],1); self.assertEqual(second['resolved_ids'],['a'])
    def test_api_surface_external_listener_is_attention(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source=root/'api.json'; state=root/'state.json'
            source.write_text(json.dumps({'live_apis':[{'port':9999,'bind_scope':'public','process':'python3','service':None,'exposure':'public','access_boundary':'unknown_review_required'}]}))
            result=api_build(source=source,state=state)
            self.assertEqual(result['state'],'attention'); self.assertFalse(result['network_mutation_performed'])
            self.assertTrue(any(x['kind']=='unexpected_exposure' for x in result['findings']))
    def test_wave6_sources_are_read_only_to_inspected_systems(self):
        root=Path(__file__).resolve().parents[1]
        for name in ['automation_watchdog_bot.py','evidence_integrity_bot.py','api_surface_health_bot.py']:
            text=(root/'tools/automation'/name).read_text()
            self.assertNotIn('systemctl restart',text); self.assertNotIn('systemctl enable',text); self.assertNotIn('UPDATE provenance_',text)
    def test_units_exist(self):
        root=Path(__file__).resolve().parents[1]
        for base in ['automation-watchdog','action-lifecycle','evidence-integrity','api-surface-health']:
            self.assertTrue((root/'deploy/automation-wave6'/f'edge1-{base}.service').is_file())
            self.assertTrue((root/'deploy/automation-wave6'/f'edge1-{base}.timer').is_file())
if __name__=='__main__': unittest.main()
