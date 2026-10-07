import importlib.util, os, sqlite3, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(n,p):
 spec=importlib.util.spec_from_file_location(n,ROOT/p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
cert=load('cert_wave2','tools/automation/certificate_expiry_bot.py')
storage=load('storage_wave2','tools/automation/storage_database_health_bot.py')
brief=load('brief_wave2','tools/automation/weekly_executive_briefing.py')
git_hygiene=load('git_hygiene_wave2','tools/automation/git_hygiene_bot.py')
class Wave2Tests(unittest.TestCase):
 def test_storage_db_health_readonly(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.sqlite'; db=sqlite3.connect(p); db.execute('create table t(x)'); db.commit(); db.close(); before=p.stat().st_mtime_ns; self.assertEqual(storage.dbhealth(p)['state'],'ok'); self.assertEqual(before,p.stat().st_mtime_ns)
 def test_weekly_briefing_is_non_authorizing(self):
  d={'generated_at':'x','summary':{'outstanding_actions':1,'high_actions':0,'backup_state':'healthy','drift_findings':0,'documents_indexed':1,'certificate_state':'healthy','storage_state':'healthy','automation_failures':0,'live_api_listeners':1},'sources_available':{'x':True}}
  self.assertIn('does not authorize changes',brief.md(d))
 def test_git_hygiene_source_allowlist_excludes_sensitive_contacts_config(self):
  self.assertTrue(git_hygiene.eligible_source('tools/automation/example.py'))
  self.assertTrue(git_hygiene.eligible_source('config/automation/public-websites.json'))
  self.assertFalse(git_hygiene.eligible_source('config/contacts/private.json'))
 def test_git_hygiene_uses_no_optional_locks(self):
  source=(ROOT/'tools/automation/git_hygiene_bot.py').read_text()
  self.assertIn("'--no-optional-locks'",source)
 def test_git_hygiene_restores_git_modes(self):
  self.assertEqual(git_hygiene.expected_mode('100644'),0o644)
  self.assertEqual(git_hygiene.expected_mode('100755'),0o755)
  self.assertIsNone(git_hygiene.expected_mode('120000'))
 def test_cert_state_threshold_shape(self):
  rows=cert.certs(); self.assertTrue(all(x['state'] in {'healthy','warning','critical'} for x in rows))
if __name__=='__main__': unittest.main()
