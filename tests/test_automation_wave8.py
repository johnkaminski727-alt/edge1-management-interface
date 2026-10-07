import unittest
from datetime import datetime, timezone
from tools.automation.security_baseline_bot import evaluate, REQUIRED_OBSERVED_SERVICES, REQUIRED_SYSTEMD
class Wave8Tests(unittest.TestCase):
    def good(self):
        now=datetime(2026,10,7,15,tzinfo=timezone.utc)
        crowd={'generated_at':now.isoformat(),'read_only':True,'traffic_controls_changed':False,'services':{x:{'active':True,'enabled':True,'observed':True} for x in REQUIRED_OBSERVED_SERVICES}}
        nft={'generated_at':now.isoformat(),'observation':{'observed':True},'errors':[],'aggregates':{'objects':{'rule':200,'set':7},'rules':{'verdicts':{'drop':20}},'elements':{'set_count':1000}}}
        canary={'remaining_blockers':[],'cutover_gates':{'inbound_security_acceptance':True},'other_domains_untouched':True}
        api={'state':'healthy','summary':{'high':0}}
        corr={'generated_at':now.isoformat()}
        spam={'last_success_utc':'20261007T041958Z','drop4':'1600','drop6':'85'}
        units={u:{'active':'active','enabled':'enabled','result':'success','exit':'0'} for u in REQUIRED_SYSTEMD}
        return now,crowd,nft,canary,api,corr,spam,units
    def test_healthy_baseline(self):
        args=self.good(); d=evaluate(*args[1:],now=args[0]); self.assertEqual(d['state'],'healthy'); self.assertFalse(d['production_mutation_performed']); self.assertFalse(d['traffic_controls_changed'])
    def test_failed_security_service_is_attention(self):
        args=list(self.good()); args[-1]=dict(args[-1]); u=REQUIRED_SYSTEMD[0]; args[-1][u]={'active':'failed','enabled':'enabled','result':'exit-code','exit':'1'}
        d=evaluate(*args[1:],now=args[0]); self.assertEqual(d['state'],'attention'); self.assertTrue(any(x['kind']=='unit_'+u for x in d['findings']))
    def test_stale_observer_is_warning(self):
        args=list(self.good()); args[1]=dict(args[1]); args[1]['generated_at']='2026-10-07T14:00:00+00:00'; d=evaluate(*args[1:],now=args[0]); self.assertEqual(d['state'],'warning')
    def test_historical_suricata_not_required(self):
        args=self.good(); d=evaluate(*args[1:],now=args[0]); self.assertFalse(d['historical_suricata_required'])
if __name__=='__main__': unittest.main()
