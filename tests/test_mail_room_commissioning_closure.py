import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from tools.messaging.mail_room_security_scan import inspect
from tools.messaging.edge1_mail_gateway_archive import merge_matching_delivery,_delivery_content_hash
from mail_edge1_gateway_source import open_edge1_store,normalize_edge1_rfc822

class ClosureTests(unittest.TestCase):
    def raw(self,recipient='one@creekco.ca',body='Same message',html=False):
        return ('From: John Kaminski <spiritcreekgardens@outlook.com>\nTo: one@creekco.ca, two@omegafx.com\nX-Original-To: '+recipient+'\nDate: Wed, 7 Oct 2026 03:37:08 +0000\nMessage-ID: <closure@example.test>\nSubject: Test\nContent-Type: '+('text/html' if html else 'text/plain')+'\n\n'+body).encode()
    def test_exact_authenticated_external_identity(self):
        config={'authenticated_external_identities':['spiritcreekgardens@outlook.com']}
        clean={'score':0,'symbols':{'R_DKIM_ALLOW':{},'DMARC_POLICY_ALLOW':{}}}
        for raw,result,expected in [(self.raw(),clean,'released'),(self.raw(),{'score':0,'symbols':{}},'quarantine'),(self.raw().replace(b'spiritcreekgardens@outlook.com',b'attacker@outlook.com'),clean,'quarantine'),(self.raw(),{**clean,'symbols':{**clean['symbols'],'PHISHING':{}}},'quarantine')]:
            decision,_,_=inspect(raw,policy_config=config,scan=lambda _: 'clean_download_disabled',spam_scan=lambda *a:result)
            self.assertEqual(decision['state'],expected)
    def test_html_text_is_inert_and_original_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            store=open_edge1_store(Path(t)/'db');raw=self.raw(body='<head><style>bad</style></head><p>Hello &amp; welcome</p><script>danger()</script>',html=True)
            record=normalize_edge1_rfc822(raw,store,envelope_recipient='one@creekco.ca')
            self.assertIn('Hello & welcome',record['body_text']);self.assertNotIn('danger',record['body_text']);self.assertNotIn('bad',record['body_text']);self.assertIn(b'<script>',raw)
    def test_archival_identity_is_bound_to_unchanged_original(self):
        from server.mail_room_security import archive_message_id
        from tools.messaging.privateemail_repair_history import projection
        import hashlib
        raw=self.raw().replace(b'<closure@example.test>',b'broken-id').replace(b'Wed, 7 Oct 2026 03:37:08 +0000',b'{smtp_date}')
        data,changes=projection(raw,'blank@ww.cx','2020-10-06T03:00:00+00:00')
        mid='<privateemail-'+hashlib.sha256(raw).hexdigest()+'@archive.ww.cx>'
        item={'source':'namecheap-private-email-imap','normalization':{'indexed_message_id':mid}}
        self.assertEqual(archive_message_id(raw,item),mid)
        self.assertEqual(changes['date_source'],'provider_imap_internaldate')
        self.assertIn(b'broken-id',raw);self.assertIn(mid.encode(),data)
        with self.assertRaises(ValueError):archive_message_id(raw+b'changed',item)
        with self.assertRaises(ValueError):archive_message_id(raw,{**item,'source':'untrusted'})
    def test_invalid_date_uses_explicit_local_receipt_only(self):
        with tempfile.TemporaryDirectory() as t:
            store=open_edge1_store(Path(t)/'db');raw=self.raw().replace(b'Wed, 7 Oct 2026 03:37:08 +0000',b'{smtp_date}')
            with self.assertRaises(Exception):normalize_edge1_rfc822(raw,store,envelope_recipient='one@creekco.ca')
            record=normalize_edge1_rfc822(raw,store,envelope_recipient='one@creekco.ca',received_at='2026-10-07T09:00:12+00:00')
            self.assertEqual(record['occurred_at'],'2026-10-07T09:00:12+00:00')
    def test_catch_all_receiving_does_not_use_sending_allowlist(self):
        from tools.messaging.mail_room_security_scan import process
        from server.mail_room_security import SecurityStore
        from unittest.mock import patch
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);security=SecurityStore(root/'security'/'db');raw=self.raw()
            for domain in ['creekco.ca','outside.test']:
                directory=root/'archive'/domain/'queue';directory.mkdir(parents=True);(directory/'message.eml').write_bytes(raw.replace(b'<closure@example.test>',('<'+domain+'@example.test>').encode()))
                content=(directory/'message.eml').read_bytes();mid='<'+domain+'@example.test>'
                (directory/'metadata.json').write_text(json.dumps({'domain':domain,'envelope_recipient':'new-address@'+domain,'rfc822_sha256':hashlib.sha256(content).hexdigest(),'normalization':{'message_id_sha256':hashlib.sha256(mid.encode()).hexdigest()}}))
            clean={'state':'released','reasons':['checks_passed'],'scan_complete':True,'hard_block':False,'authentication':{'status':'not_verified'}}
            with patch('tools.messaging.mail_room_security_scan.inspect',side_effect=lambda *a: (dict(clean,reasons=['checks_passed']),[],[])),patch('tools.messaging.mail_room_security_scan.scanner_ready',return_value=True):
                process(root/'archive',security,root/'drafts',{'allowed_recipients':['contact@creekco.ca'],'catch_all_domains':['creekco.ca']})
            self.assertEqual(security.get('<creekco.ca@example.test>')['state'],'released')
            self.assertEqual(security.get('<outside.test@example.test>')['state'],'quarantine')
    def test_archived_attachment_holds_cannot_be_released_by_clean_rescan(self):
        from tools.messaging.mail_room_security_scan import process
        from server.mail_room_security import SecurityStore
        from unittest.mock import patch
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);directory=root/'archive'/'creekco.ca'/'queue';directory.mkdir(parents=True);raw=self.raw();mid='<closure@example.test>'
            (directory/'message.eml').write_bytes(raw)
            (directory/'metadata.json').write_text(json.dumps({'domain':'creekco.ca','envelope_recipient':'one@creekco.ca','rfc822_sha256':hashlib.sha256(raw).hexdigest(),'normalization':{'message_id_sha256':hashlib.sha256(mid.encode()).hexdigest(),'import_security_hold':True}}))
            store=SecurityStore(root/'security'/'db');clean={'state':'released','reasons':['checks_passed'],'scan_complete':True,'hard_block':False}
            with patch('tools.messaging.mail_room_security_scan.inspect',return_value=(clean,[],[])),patch('tools.messaging.mail_room_security_scan.scanner_ready',return_value=True):process(root/'archive',store,root/'drafts',{'catch_all_domains':['creekco.ca']})
            result=store.get(mid);self.assertEqual(result['state'],'quarantine');self.assertTrue(result['hard_block']);self.assertFalse(result['scan_complete'])
            with self.assertRaises(ValueError):store.action(mid,'release')
    def test_matching_deliveries_merge_but_changed_content_does_not(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db=root/'db';archives=root/'archive';directory=archives/'creekco.ca'/'queue';directory.mkdir(parents=True)
            raw=self.raw();record=normalize_edge1_rfc822(raw,open_edge1_store(db),envelope_recipient='one@creekco.ca')
            import hashlib
            (directory/'message.eml').write_bytes(raw);(directory/'metadata.json').write_text(json.dumps({'rfc822_sha256':hashlib.sha256(raw).hexdigest(),'normalization':{'status':'ingested','message_id_sha256':hashlib.sha256(record['message_id'].encode()).hexdigest()}}))
            merged,duplicate=merge_matching_delivery(self.raw('two@omegafx.com'),archives,db,'two@omegafx.com')
            self.assertEqual(set(merged['recipients']),{'one@creekco.ca','two@omegafx.com'});self.assertEqual(duplicate,'creekco.ca/queue')
            self.assertEqual(merge_matching_delivery(self.raw('three@ww.cx','Different message'),archives,db,'three@ww.cx'),(None,None))
            self.assertEqual(merge_matching_delivery(self.raw('three@ww.cx','Same message\nAttachment changed'),archives,db,'three@ww.cx'),(None,None))
            with self.assertRaises(Exception):merge_matching_delivery(self.raw('wrong@ww.cx'),archives,db,'three@ww.cx')

if __name__=='__main__':unittest.main()
