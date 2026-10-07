import unittest
from datetime import datetime, timedelta, timezone
from tools.automation.service_self_heal_bot import transient_cleanup_candidate, TRANSIENT_MIN_AGE_SECONDS
class SelfHealTransientTests(unittest.TestCase):
    def props(self,when,**overrides):
        p={'ActiveState':'failed','Transient':'yes','UnitFileState':'transient','FragmentPath':'/run/systemd/transient/test.service','StateChangeTimestamp':when.strftime('%a %Y-%m-%d %H:%M:%S GMT')}; p.update(overrides); return p
    def test_old_transient_failure_is_eligible(self):
        now=datetime(2026,10,7,15,tzinfo=timezone.utc); ok,age=transient_cleanup_candidate(self.props(now-timedelta(seconds=TRANSIENT_MIN_AGE_SECONDS+1)),now); self.assertTrue(ok); self.assertGreaterEqual(age,TRANSIENT_MIN_AGE_SECONDS)
    def test_recent_transient_failure_is_not_eligible(self):
        now=datetime(2026,10,7,15,tzinfo=timezone.utc); ok,_=transient_cleanup_candidate(self.props(now-timedelta(seconds=60)),now); self.assertFalse(ok)
    def test_persistent_unit_is_never_eligible(self):
        now=datetime(2026,10,7,15,tzinfo=timezone.utc); ok,_=transient_cleanup_candidate(self.props(now-timedelta(hours=1),Transient='no',UnitFileState='enabled',FragmentPath='/usr/lib/systemd/system/x.service'),now); self.assertFalse(ok)
    def test_transient_outside_run_path_is_not_eligible(self):
        now=datetime(2026,10,7,15,tzinfo=timezone.utc); ok,_=transient_cleanup_candidate(self.props(now-timedelta(hours=1),FragmentPath='/etc/systemd/system/x.service'),now); self.assertFalse(ok)
if __name__=='__main__':unittest.main()
