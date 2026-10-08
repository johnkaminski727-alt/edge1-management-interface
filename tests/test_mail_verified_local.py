import unittest
from server.mail_room_security import classify, verified_local_submission

class VerifiedLocalTests(unittest.TestCase):
    def test_evidence(self):
        policy={'local_submission_domains':['ww.cx']}
        evidence={'source':'postfix_pipe','client_ip':'127.0.0.1','envelope_sender':'john@ww.cx'}
        self.assertTrue(verified_local_submission(evidence,'john@ww.cx',policy))
        for bad in [None,{**evidence,'source':'import'},{**evidence,'client_ip':'89.126.248.191'},{**evidence,'client_ip':'invalid'},{**evidence,'envelope_sender':'MAILER-DAEMON'}]:
            self.assertFalse(verified_local_submission(bad,'john@ww.cx',policy))
        self.assertFalse(verified_local_submission(evidence,'spoof@ww.cx',policy))
        self.assertFalse(verified_local_submission(evidence,'john@ww.cx',{}))
    def test_security_and_explicit_filter_holds(self):
        base={'score':7.9,'symbols':{},'action':'add header'}
        self.assertEqual(classify(base,['clean'])['state'],'junk')
        self.assertEqual(classify(base,['clean'],verified_local=True)['state'],'released')
        for symbols in [{'PHISHING':{}},{'DMARC_POLICY_REJECT':{}},{'GTUBE':{}}]:
            self.assertNotEqual(classify({**base,'symbols':symbols},['clean'],verified_local=True)['state'],'released')
        for state in ['quarantined','oversize_blocked','policy_blocked','unscanned_blocked']:
            self.assertNotEqual(classify(base,[state],verified_local=True)['state'],'released')
        for change in [{'score':16},{'action':'reject'},{'action':'quarantine'},{'action':'soft reject'},{'is_skipped':True},{'symbols':{'DKIM_TEMPFAIL':{}}}]:
            self.assertNotEqual(classify({**base,**change},['clean'],verified_local=True)['state'],'released')
