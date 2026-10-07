import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(n,p):
 spec=importlib.util.spec_from_file_location(n,ROOT/p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
heal=load('heal_wave3','tools/automation/service_self_heal_bot.py')
know=load('know_wave3','tools/automation/knowledge_consolidation_bot.py')
mail=load('mail_wave3','tools/automation/mail_domain_health_bot.py')
class Wave3Tests(unittest.TestCase):
 def test_self_heal_only_failed_enabled_after_cooldown(self):
  self.assertFalse(heal.should_repair({'ActiveState':'active','UnitFileState':'enabled'},0,10000))
  self.assertFalse(heal.should_repair({'ActiveState':'failed','UnitFileState':'disabled'},0,10000))
  self.assertFalse(heal.should_repair({'ActiveState':'failed','UnitFileState':'enabled'},9500,10000))
  self.assertTrue(heal.should_repair({'ActiveState':'failed','UnitFileState':'enabled'},0,10000))
 def test_title_normalization(self):
  self.assertEqual(know.norm_title('Ava Daily — Briefing!'),'ava daily briefing')
 def test_mail_health_contract_shape(self):
  d=mail.build(); self.assertEqual(d['contract'],'wwcx.mail-domain-health.v1'); self.assertFalse(d['secrets_exposed']); self.assertFalse(d['mutation_performed'])
 def test_managed_document_titles_do_not_create_false_conflicts(self):
  self.assertEqual(know.norm_title('Calendar — invite.ics'),'calendar invite ics')
if __name__=='__main__': unittest.main()
