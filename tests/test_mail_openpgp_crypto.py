import pathlib,subprocess,tempfile,unittest
from server.mail_openpgp_crypto import GPGEngine
class TestCrypto(unittest.TestCase):
 def test_disposable_encrypt_decrypt(self):
  with tempfile.TemporaryDirectory() as td:
   home=pathlib.Path(td);home.chmod(0o700)
   subprocess.run(['gpg','--batch','--yes','--pinentry-mode','loopback','--passphrase','','--homedir',td,'--quick-generate-key','WWCX Test <openpgp-test@ww.cx>','rsa3072','sign,encr','1d'],check=True,capture_output=True)
   engine=GPGEngine(home);fps=engine.fingerprints(True);self.assertTrue(fps)
   ciphertext=engine.encrypt(b'synthetic secret', [fps[0]], fps[0]);self.assertIn(b'BEGIN PGP MESSAGE',ciphertext)
   self.assertEqual(engine.decrypt(ciphertext),b'synthetic secret')
   signature=engine.sign(b'synthetic signed content',fps[0]);self.assertIn(b'BEGIN PGP SIGNATURE',signature)
   data=home/'signed.txt';sig=home/'signed.asc';data.write_bytes(b'synthetic signed content');sig.write_bytes(signature)
   verified=subprocess.run(['gpg','--batch','--homedir',td,'--verify',str(sig),str(data)],capture_output=True)
   self.assertEqual(verified.returncode,0)
if __name__=='__main__': unittest.main()
