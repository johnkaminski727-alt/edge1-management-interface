import importlib.util, unittest
from datetime import datetime, timezone
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
 def test_operational_authoritative_dns_is_healthy(self):
  original=mail.load
  now=datetime.now(timezone.utc).isoformat()
  def fake(path):
   if path==mail.IDENT: return {'domains':{'ww.cx':{}}}
   if path==mail.GATE: return {'generated_at':now,'domains':[{'domain':'ww.cx','commissioned':True,'sending_enabled':True,'migration_state':'live_on_edge1','checks':{},'mx_answer_count':1}],'services':{},'backlog':{'pending_or_unchecked':0}}
   if path==mail.DNS: return {'authoritative_dns':{'enabled':True,'state':'operational','wireguard_split_dns_preserved':True},'resolver':{'adguard_active':True,'unbound_active':True}}
   return {}
  try:
   mail.load=fake; d=mail.build()
  finally:
   mail.load=original
  self.assertEqual(d['state'],'healthy')
  self.assertNotIn('authoritative_dns_attention',d['warnings'])
 def test_mail_health_contract_shape(self):
  d=mail.build(); self.assertEqual(d['contract'],'wwcx.mail-domain-health.v1'); self.assertFalse(d['secrets_exposed']); self.assertFalse(d['mutation_performed'])
 def test_managed_document_titles_do_not_create_false_conflicts(self):
  self.assertEqual(know.norm_title('Calendar — invite.ics'),'calendar invite ics')
if __name__=='__main__': unittest.main()
