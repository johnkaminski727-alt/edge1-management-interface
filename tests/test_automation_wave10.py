import unittest
from datetime import datetime, timezone
from tools.automation.update_readiness_bot import apt_upgrades, evaluate, simulation_plan
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

    def test_simulated_transaction_is_non_mutating(self):
        text='Inst openssl [1] (2 stable-security [amd64])\nInst linux-image-test (1 stable-security [amd64])\n13 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\n'
        plan=simulation_plan(text)
        self.assertTrue(plan['success']); self.assertEqual(plan['counts']['upgraded'],13); self.assertEqual(plan['counts']['newly_installed'],1)
        self.assertFalse(plan['removals_planned']); self.assertFalse(plan['package_install_authorized']); self.assertFalse(plan['mutation_performed'])
    def test_simulated_transaction_surfaces_removals(self):
        plan=simulation_plan('Remv obsolete [1]\n0 upgraded, 0 newly installed, 1 to remove and 0 not upgraded.\n')
        self.assertTrue(plan['removals_planned']); self.assertEqual(plan['removal_packages'],['obsolete'])
    def test_reboot_never_authorized(self):
        d=evaluate([],[],True,['linux-image'], 'kernel',1,datetime(2026,10,7,tzinfo=timezone.utc))
        self.assertEqual(d['state'],'attention'); self.assertFalse(d['reboot_authorized']); self.assertFalse(d['reboot_performed'])
if __name__=='__main__':unittest.main()
