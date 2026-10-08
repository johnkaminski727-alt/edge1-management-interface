import unittest,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from mail_correspondence_store import MailCorrespondenceStore,strip_newsletter_links,LINK_REMOVAL_NOTICE
from mail_room_security import SecurityStore
class NewsletterLinks(unittest.TestCase):
 def test_scoped_idempotent_and_keeps_text(self):
  body='Save on seeds! (HTTPS://cl.exct.net/?qs=abc)\nVisit www.wbu.com/store\nCall 604-792-1239. https://\n'
  clean=strip_newsletter_links('ChilliwackBC430@email.wbu.com',body)
  self.assertNotRegex(clean,r'(?i)https?://|www\.')
  self.assertIn('Save on seeds!',clean);self.assertIn('604-792-1239',clean)
  self.assertEqual(strip_newsletter_links('chilliwackbc430@email.wbu.com',clean),clean)
  self.assertEqual(strip_newsletter_links('attacker@example.test',body),body)
  self.assertEqual(strip_newsletter_links('chilliwackbc430@email.wbu.com.evil.test',body),body)
  self.assertEqual(strip_newsletter_links('chilliwackbc430@email.wbu.com',body,'outbound'),body)
 def test_intake_projection_never_releases_security(self):
  with tempfile.TemporaryDirectory() as td:
   store=MailCorrespondenceStore(Path(td)/'mail.sqlite3',source='test-native',source_authoritative=True,source_scope='local_native')
   mid='<newsletter@test.example>'
   payload={'message_id':mid,'thread_id':'THREAD-TEST-001','direction':'inbound','sender':'ChilliwackBC430@email.wbu.com','recipients':['john@ww.cx'],'subject':'Seed sale','body_text':'Save on seeds https://cl.exct.net/abc','references':[],'occurred_at':'2026-10-08T04:00:00+00:00'}
   store.ingest(payload);self.assertIn(LINK_REMOVAL_NOTICE,store.read_message(mid)['body_text']);self.assertIn('https://',payload['body_text'])
   security=SecurityStore(Path(td)/'security.sqlite3');self.assertEqual(security.get(mid)['state'],'pending')
if __name__=='__main__':unittest.main()
