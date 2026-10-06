import base64, unittest
from email import policy
from email.message import EmailMessage
from server import mail_openpgp_mime
from server import mail_openpgp_socket_adapter as adapter

class TestAdapter(unittest.TestCase):
    def message(self):
        m=EmailMessage(policy=policy.SMTP)
        m['From']='john@ww.cx';m['To']='recipient@example.net';m['Subject']='PGP test';m['Message-ID']='<pgp-test@ww.cx>'
        m.set_content('secret body')
        return m.as_bytes(policy=policy.SMTP)
    def fake(self,request):
        self.assertEqual(request['operation'],'encrypt')
        return {'ciphertext_b64':base64.b64encode(b'-----BEGIN PGP MESSAGE-----\nsynthetic\n-----END PGP MESSAGE-----\n').decode(),'operation':'sign_encrypt'}
    def test_builds_pgp_mime_and_preserves_outer_headers(self):
        out=adapter.transform(self.message(),{'operation':'sign_encrypt','signing_fingerprint':'A'*40,'recipient_fingerprints':['B'*40]},rpc=self.fake)
        state=mail_openpgp_mime.detect(out['mime_bytes'])
        self.assertTrue(state['encrypted'])
        self.assertIn(b'Subject: PGP test',out['mime_bytes'])
        self.assertNotIn(b'secret body',out['mime_bytes'])
    def test_missing_recipient_key_fails(self):
        with self.assertRaises(adapter.OpenPGPAdapterError):
            adapter.transform(self.message(),{'operation':'encrypt','recipient_fingerprints':[]},rpc=self.fake)

if __name__=='__main__': unittest.main()
