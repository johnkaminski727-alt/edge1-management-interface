import unittest
from datetime import datetime, timezone
from tools.automation.domain_renewal_monitor import evaluate

class Wave9Tests(unittest.TestCase):
    def test_long_lived_domains_are_healthy(self):
        now=datetime(2026,10,7,tzinfo=timezone.utc)
        d=evaluate([{'domain':'example.com','expiration':'2028-10-07T00:00:00Z'}],now)
        self.assertEqual(d['state'],'healthy')
        self.assertFalse(d['registrar_mutation_performed'])
        self.assertFalse(d['automatic_renewal_authorized'])
    def test_30_day_expiry_is_attention(self):
        now=datetime(2026,10,7,tzinfo=timezone.utc)
        d=evaluate([{'domain':'example.com','expiration':'2026-10-25T00:00:00Z'}],now)
        self.assertEqual(d['state'],'attention')
        self.assertEqual(d['summary']['expiring_30d'],1)
    def test_lookup_failure_is_warning(self):
        d=evaluate([{'domain':'example.com','error':'timeout'}],datetime(2026,10,7,tzinfo=timezone.utc))
        self.assertEqual(d['state'],'warning')
        self.assertEqual(d['summary']['lookup_failures'],1)
    def test_180_day_window_is_stage_only(self):
        now=datetime(2026,10,7,tzinfo=timezone.utc)
        d=evaluate([{'domain':'example.com','expiration':'2027-02-01T00:00:00Z'}],now)
        self.assertEqual(d['state'],'healthy')
        self.assertEqual(d['summary']['expiring_180d'],1)
        self.assertEqual(d['findings'][0]['action_level'],'AUTO-STAGE')
if __name__=='__main__': unittest.main()
