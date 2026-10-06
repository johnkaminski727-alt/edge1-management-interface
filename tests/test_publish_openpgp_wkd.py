import pathlib,tempfile,unittest
from unittest import mock
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/messaging'))
import publish_openpgp_wkd as M
class T(unittest.TestCase):
 def test_hash_restricts_domain(self):
  with self.assertRaises(M.WKDError): M.wkd_hash('x@example.net')
 def test_dearmor_rejects_private(self):
  with self.assertRaises(M.WKDError): M.dearmor_public('-----BEGIN PGP PRIVATE KEY BLOCK-----')
 def test_publish_layout(self):
  key={'email_address':'john@ww.cx','fingerprint':'A'*40,'verification_status':'verified','public_key_armored':'-----BEGIN PGP PUBLIC KEY BLOCK-----\nX\n-----END PGP PUBLIC KEY BLOCK-----\n'}
  with tempfile.TemporaryDirectory() as td, mock.patch.object(M,'load_key',return_value=key), mock.patch.object(M,'wkd_hash',return_value='hashvalue'), mock.patch.object(M,'dearmor_public',return_value=b'PUBLIC'):
   out=M.publish(pathlib.Path('/x'),696,pathlib.Path(td))
   self.assertEqual(out['wkd_hash'],'hashvalue')
   self.assertEqual((pathlib.Path(td)/'.well-known/openpgpkey/ww.cx/hu/hashvalue').read_bytes(),b'PUBLIC')
   self.assertEqual((pathlib.Path(td)/'.well-known/openpgpkey/ww.cx/policy').read_bytes(),b'')
if __name__=='__main__': unittest.main()
