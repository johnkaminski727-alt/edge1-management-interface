import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from mail_correspondence_store import MailCorrespondenceStore, CorrespondenceStoreError
from server.mail_room_security import SecurityStore, classify, rspamd_scan, message_hash
from server.mail_room_features import MailRoomFeatures
from server.mail_room_http import DraftStore
from tools.messaging.mail_room_security_scan import inspect

RAW=b'From: person@example.test\nTo: john@ww.cx\nMessage-ID: <one@example.test>\nAuthentication-Results: trusted; spf=pass; dkim=pass; dmarc=pass\nContent-Type: text/plain\n\nUntrusted content\n'
CLEAN={'state':'released','reasons':['checks_passed'],'authentication':{'status':'not_verified'},'scan_complete':True,'hard_block':False}


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.security=SecurityStore(self.root/'security'/'security.sqlite3')
        self.path=self.root/'mail'/'mail.sqlite3'
        self.writer=MailCorrespondenceStore(self.path,source='fixture',source_authoritative=True,source_scope='production_native')
        self.ids=['<one@example.test>','<two@example.test>','<three@example.test>']
        for mid in self.ids:
            self.writer.ingest({'message_id':mid,'thread_id':'THREAD-FIXTURE-001','direction':'inbound','sender':'person@example.test','recipients':['john@ww.cx'],'subject':'Example','body_text':'Private body '+mid,'references':[],'occurred_at':'2026-10-05T20:00:00Z'})
        self.env=patch.dict(os.environ,{'WWCX_MAIL_SECURITY_REQUIRED':'true','WWCX_MAIL_SECURITY_DATABASE':str(self.security.path)});self.env.start()
        self.reader=MailCorrespondenceStore(self.path,source='reader',read_only=True)
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def test_gate_filters_all_reads_and_mixed_threads(self):
        self.assertEqual(self.reader.search_authoritative()['count'],0)
        with self.assertRaises(CorrespondenceStoreError):self.reader.read_message(self.ids[0])
        with self.assertRaises(CorrespondenceStoreError):self.reader.read_thread('THREAD-FIXTURE-001')
        self.security.write(self.ids[0],'a'*64,CLEAN)
        self.security.write(self.ids[1],'b'*64,{**CLEAN,'state':'junk'})
        self.assertEqual([m['message_id'] for m in self.reader.search_authoritative()['messages']],[self.ids[0]])
        self.assertEqual([m['message_id'] for m in self.reader.read_thread('THREAD-FIXTURE-001')['messages']],[self.ids[0]])
        self.security.path.rename(self.security.path.with_suffix('.offline'))
        with self.assertRaises(CorrespondenceStoreError):self.reader.search_authoritative()
    def test_inbox_folders_do_not_bypass_ava_gate(self):
        self.security.write(self.ids[0],'a'*64,CLEAN)
        self.security.write(self.ids[1],'b'*64,{**CLEAN,'state':'junk'})
        prefs=DraftStore(self.root/'drafts.sqlite3')
        features=MailRoomFeatures(prefs,self.path,{'domains':{'ww.cx':{}}})
        self.assertEqual([m['message_id'] for m in features.messages({})['messages']],[self.ids[0]])
        self.assertEqual([m['message_id'] for m in features.messages({'folder':['all']})['messages']],[self.ids[0]])
        self.assertEqual([m['message_id'] for m in features.messages({'folder':['junk']})['messages']],[self.ids[1]])
        self.assertEqual([m['message_id'] for m in features.messages({'folder':['pending']})['messages']],[self.ids[2]])
    def test_trash_restore_preserves_security_and_source(self):
        prefs=DraftStore(self.root/'trash-drafts.sqlite3')
        features=MailRoomFeatures(prefs,self.path,{'domains':{'ww.cx':{}}})
        states=['released','junk','quarantine']
        for mid,state in zip(self.ids,states):
            self.security.write(mid,'a'*64,{**CLEAN,'state':state})
            features.flags({'message_id':mid,'archived':True,'deleted':True})
        for folder in ['inbox','archive','all','junk','quarantine','pending']:
            self.assertEqual(features.messages({'folder':[folder]})['messages'],[])
        trash=features.messages({'folder':['trash']})['messages']
        self.assertEqual(len(trash),3)
        self.assertTrue(all(m['deleted'] and 'body_text' not in m for m in trash))
        features.flags({'message_id':self.ids[1],'deleted':False})
        self.assertEqual([m['message_id'] for m in features.messages({'folder':['junk']})['messages']],[self.ids[1]])
        with self.security.connect() as db:
            self.assertEqual([db.execute('SELECT state FROM decisions WHERE message_hash=?',(message_hash(mid),)).fetchone()[0] for mid in self.ids],states)
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('SELECT count(*) FROM correspondence').fetchone()[0],3)
        with self.assertRaises(ValueError):features.flags({'message_id':self.ids[0],'deleted':'true'})

    def test_phishing_report_survives_rescans_and_related_holds(self):
        for mid in self.ids[:2]:self.security.write(mid,'a'*64,CLEAN,[('url','shared-link-hash')])
        result=self.security.action(self.ids[0],'phishing',True)
        self.assertEqual(result['related_flagged'],1)
        self.assertEqual(self.security.get(self.ids[1])['state'],'quarantine')
        self.security.write(self.ids[0],'a'*64,CLEAN)
        self.assertEqual(self.security.get(self.ids[0])['state'],'quarantine')
        with self.assertRaises(CorrespondenceStoreError):self.reader.read_message(self.ids[0])
        self.security.action(self.ids[0],'spam');self.security.write(self.ids[0],'a'*64,CLEAN)
        self.assertEqual(self.security.get(self.ids[0])['state'],'quarantine')
        self.security.action(self.ids[0],'confirmed_phishing')
        with self.assertRaises(ValueError):self.security.action(self.ids[0],'release')
    def test_no_release_of_malware_or_incomplete_scans(self):
        for decision in [{**CLEAN,'state':'quarantine','hard_block':True},{**CLEAN,'state':'pending','scan_complete':False}]:
            self.security.write(self.ids[0],'a'*64,decision)
            for action in ['not_spam','release']:
                with self.assertRaises(ValueError):self.security.action(self.ids[0],action)
        self.security.write(self.ids[1],'b'*64,{**CLEAN,'state':'junk'})
        self.assertEqual(self.security.action(self.ids[1],'not_spam')['state'],'released')
        self.security.write(self.ids[1],'b'*64,{**CLEAN,'state':'junk'})
        self.assertEqual(self.security.get(self.ids[1])['state'],'released')
    def test_missing_report_and_collision_fail_closed(self):
        self.security.action(self.ids[2],'phishing');self.security.write(self.ids[2],'c'*64,CLEAN)
        self.assertEqual(self.security.get(self.ids[2])['state'],'quarantine')
        self.security.write(self.ids[0],'a'*64,CLEAN);self.security.write(self.ids[0],'b'*64,CLEAN);self.security.write(self.ids[0],'b'*64,CLEAN)
        self.assertTrue(self.security.get(self.ids[0])['hard_block'])

    def test_reviewed_release_survives_same_findings_but_not_new_risks(self):
        held={**CLEAN,'state':'quarantine','reasons':['unregistered_catch_all_recipient_review']}
        self.security.write(self.ids[0],'a'*64,held)
        self.security.action(self.ids[0],'release')
        self.security.write(self.ids[0],'a'*64,held)
        self.assertEqual(self.security.get(self.ids[0])['state'],'released')
        self.security.write(self.ids[0],'a'*64,{**held,'reasons':['new_phishing_finding'],'symbols':['PHISHING']})
        self.assertEqual(self.security.get(self.ids[0])['state'],'quarantine')
    def test_authentication_and_scan_failures(self):
        clean={'score':0,'symbols':{},'action':'no action'}
        decision,_,_=inspect(RAW,scan=lambda _: 'clean_download_disabled',spam_scan=lambda *a:clean)
        self.assertEqual(decision['authentication']['status'],'not_verified')
        decision,_,_=inspect(RAW,scan=lambda _: 'unscanned_blocked',spam_scan=lambda *a:clean)
        self.assertEqual(decision['state'],'pending');self.assertFalse(decision['scan_complete'])
        authenticated={**clean,'symbols':{'R_SPF_ALLOW':{},'DMARC_POLICY_ALLOW':{}}}
        self.assertEqual(classify(authenticated,[],transport=None)['authentication']['status'],'not_verified')
        self.assertEqual(classify(authenticated,[],transport={'source':'postfix_pipe','client_ip':'1.2.3.4'})['authentication']['status'],'domain_authenticated')
        self.assertEqual(classify({**clean,'symbols':{'PHISHING':{}}},[])['state'],'quarantine')
        self.assertEqual(classify({**clean,'score':8},[])['state'],'junk')
        self.assertEqual(classify({**clean,'symbols':{'DKIM_TEMPFAIL':{}}},[])['state'],'pending')
        rejected=classify({**clean,'score':15,'symbols':{'GTUBE':{}},'action':'reject','is_skipped':True},[])
        self.assertEqual(rejected['state'],'quarantine');self.assertFalse(rejected['scan_complete'])
    def test_embedded_file_policy_and_whole_message_scanning(self):
        raw=RAW.replace(b'Content-Type: text/plain',b'Content-Type: application/octet-stream\nContent-Disposition: inline; filename="attack.ps1"')
        decision,parts,_=inspect(raw,scan=lambda _: 'clean_download_disabled',spam_scan=lambda *a:{'score':0,'symbols':{}})
        self.assertEqual(parts[0]['state'],'policy_blocked');self.assertTrue(decision['hard_block'])
        decision,_,_=inspect(RAW,scan=lambda _: 'quarantined',spam_scan=lambda *a:{'score':0,'symbols':{}})
        self.assertEqual(decision['state'],'quarantine')
    def test_transport_not_inferred_from_forged_headers(self):
        requests=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return b'{"score":0,"symbols":{},"is_skipped":false}'
        with patch('urllib.request.urlopen',side_effect=lambda req,**kw:(requests.append(req) or Response())):
            rspamd_scan(RAW)
            rspamd_scan(RAW,{'source':'postfix_pipe','client_ip':'192.0.2.5','envelope_sender':'person@example.test'})
        self.assertNotIn('Ip',requests[0].headers);self.assertIn('SPF_CHECK',requests[0].headers['Settings'])
        self.assertEqual(requests[1].headers['Ip'],'192.0.2.5')
    def test_per_domain_settings_validation(self):
        data={'domain':'ww.cx','junk_score':5,'quarantine_score':12,'trusted_senders':['person@example.test']}
        self.security.settings(data)
        self.assertEqual(self.security.settings()['domains']['ww.cx']['junk_score'],5)
        for invalid in [{**data,'domain':'external.test'},{**data,'junk_score':0},{**data,'quarantine_score':4},{**data,'trusted_senders':['*']}]:
            with self.assertRaises(ValueError):self.security.settings(invalid)

    def test_http_review_requires_acknowledgement_and_never_calls_ava(self):
        from http.server import ThreadingHTTPServer
        from server.mail_room_http import make_handler,PREFIX
        import threading
        import urllib.request
        import urllib.error
        prefs=DraftStore(self.root/'drafts.sqlite3')
        features=MailRoomFeatures(prefs,self.path,{'domains':{'ww.cx':{}}})
        class Mail:
            def correspondence_message(inner,*,message_id):return self.reader.read_message(message_id)
        class Assistant:
            def assist(*args):raise AssertionError('Review called AI')
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Mail(),prefs,'k'*48,features,Assistant(),self.security))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(route,data,key='k'*48):
            req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+PREFIX+route,data=json.dumps(data).encode(),headers={'X-Mail-Room-Proxy-Key':key,'Content-Type':'application/json','Origin':'https://edge1.ww.cx','X-Mail-Room-Request':'1'})
            try:
                with urllib.request.urlopen(req) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as e:return e.code,json.load(e)
        try:
            self.assertEqual(request('review',{'message_id':self.ids[0],'acknowledged':False})[0],400)
            self.assertEqual(request('review',{'message_id':self.ids[0],'acknowledged':True},key='')[0],403)
            status,result=request('review',{'message_id':self.ids[0],'acknowledged':True})
            self.assertEqual(status,200);self.assertFalse(result['ai_available']);self.assertFalse(result['downloads_enabled'])
            self.security.write(self.ids[0],'a'*64,CLEAN)
            self.assertEqual(request('security-action',{'message_id':self.ids[0],'action':'phishing','interacted':True})[0],200)
            with self.assertRaises(CorrespondenceStoreError):self.reader.read_message(self.ids[0])
            self.assertEqual(request('security-action',{'message_id':self.ids[0],'action':'release'})[0],400)
            self.assertEqual(request('security-action',{'message_id':self.ids[0],'action':'release','reviewed':True})[0],200)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
