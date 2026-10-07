import unittest
from datetime import datetime, timezone
from tools.automation.update_readiness_bot import apt_upgrades, evaluate
class Wave10Tests(unittest.TestCase):
    def test_parse_security_upgrade(self):
        rows=apt_upgrades('Listing...\nopenssl/stable-security 3.5.7 amd64 [upgradable from: 3.5.6]\n')
        self.assertEqual(len(rows),1); self.assertTrue(rows[0]['security']); self.assertEqual(rows[0]['package'],'openssl')
    def test_security_updates_are_warning_stage_only(self):
        rows=[{'package':'openssl','security':True,'kernel':False,'suite':'stable-security','old_version':'1','new_version':'2','arch':'amd64'}]
        d=evaluate(rows,[],False,(), 'kernel',1,datetime(2026,10,7,tzinfo=timezone.utc))
        self.assertEqual(d['state'],'warning'); self.assertFalse(d['package_install_authorized']); self.assertFalse(d['package_mutation_performed'])
    def test_persistent_failed_unit_is_attention_but_transient_is_not(self):
        rows=[{'unit':'real.service','transient':False},{'unit':'test.service','transient':True}]
        d=evaluate([],rows,False,(), 'kernel',1,datetime(2026,10,7,tzinfo=timezone.utc))
        self.assertEqual(d['state'],'attention'); self.assertEqual(d['summary']['persistent_failed_units'],1); self.assertEqual(d['summary']['transient_failed_units'],1)
    def test_reboot_never_authorized(self):
        d=evaluate([],[],True,['linux-image'], 'kernel',1,datetime(2026,10,7,tzinfo=timezone.utc))
        self.assertEqual(d['state'],'attention'); self.assertFalse(d['reboot_authorized']); self.assertFalse(d['reboot_performed'])
if __name__=='__main__':unittest.main()
