import pathlib,tempfile,unittest
from unittest import mock
import sys,json
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/messaging'))
import activate_openpgp_sign_only as M
class T(unittest.TestCase):
 def test_not_ready_when_missing_secret(self):
  with tempfile.TemporaryDirectory() as td:
   import sqlite3
   db=pathlib.Path(td)/'x.sqlite';c=sqlite3.connect(db);c.executescript('create table contact_openpgp_keys(contact_point_id int,fingerprint text,verification_status text,revoked_at text,created_at text,id int);create table contact_openpgp_policy(contact_point_id int,mode text);');c.execute("insert into contact_openpgp_keys values(696,?, 'verified',null,'x',1)",('A'*40,));c.execute("insert into contact_openpgp_policy values(696,'sign_only')");c.commit();c.close()
   pub=pathlib.Path(td)/'pub';pub.mkdir();(pub/'john-wwcx.asc').write_text('x');(pub/'john-wwcx.json').write_text('{}')
   with mock.patch.object(M,'rpc_status',return_value={'secret_key_count':0,'encrypt_enabled':False,'decrypt_enabled':False}):
    s=M.readiness(db,696,pathlib.Path('/x'),pub);self.assertFalse(s['ready'])
 def test_apply_config_never_enables_encrypt_decrypt(self):
  cfg={'contract':'wwcx.openpgp-crypto-service.v1','encrypt_enabled':False,'decrypt_enabled':False,'sign_enabled':False,'allow_private_key_export':False}
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'c.json';p.write_text(json.dumps(cfg));self.assertFalse(M.read_json(p)['sign_enabled'])
if __name__=='__main__':unittest.main()
