import hashlib,json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from tools.messaging.mail_room_reviewed_scan import reviewed_scan, definitions_key
class ReviewedScanTests(unittest.TestCase):
 def test_exact_bytes_permissions_definitions_and_failure(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);defs=p/'defs';defs.mkdir();(defs/'daily.cld').write_bytes(b'definitions')
   config=p/'reviews.json';raw=b'From: test@example.test\n\nreviewed'
   digest=hashlib.sha256(raw).hexdigest()
   config.write_text(json.dumps({digest:{'approved':True,'raw_sha256':digest}}));config.chmod(0o600)
   calls=[]
   def clean(*a,**kw):calls.append(a);return SimpleNamespace(returncode=0,stdout=b'OK',stderr=b'')
   self.assertFalse(reviewed_scan(b'changed',config,defs,clean));self.assertFalse(calls)
   self.assertTrue(reviewed_scan(raw,config,defs,clean));self.assertEqual(len(calls),1)
   self.assertTrue(reviewed_scan(raw,config,defs,clean));self.assertEqual(len(calls),1)
   config.chmod(0o644);self.assertFalse(reviewed_scan(raw,config,defs,clean));config.chmod(0o600)
   (defs/'daily.cld').write_bytes(b'new definitions')
   bad=lambda *a,**kw:SimpleNamespace(returncode=1,stdout=b'FOUND',stderr=b'')
   self.assertFalse(reviewed_scan(raw,config,defs,bad))
   self.assertFalse(json.loads(config.read_text())[digest]['clean'])
   def timeout(*a,**kw):raise subprocess.TimeoutExpired('scan',120)
   self.assertFalse(reviewed_scan(raw,config,defs,timeout))
 def test_no_approval_no_scan(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);f=p/'reviews.json';f.write_text('{}');f.chmod(0o600)
   def forbidden(*a,**kw):raise AssertionError('Unapproved rescan')
   self.assertFalse(reviewed_scan(b'new',f,p,forbidden))
if __name__=='__main__':unittest.main()
