import pathlib,sqlite3,tempfile,unittest
from tools.messaging.register_openpgp_public_key import register,RegistrationError
from tools.unified_contacts.schema_openpgp import apply_schema
class TestRegister(unittest.TestCase):
 def db(self):
  td=tempfile.TemporaryDirectory();db=pathlib.Path(td.name)/'c.sqlite';con=sqlite3.connect(db);con.execute('create table contact_points(id integer primary key,point_type text,normalized_value text)');con.execute("insert into contact_points values(696,'email','john@ww.cx')");apply_schema(con);con.commit();con.close();return td,db
 def test_register_public_metadata(self):
  td,db=self.db();self.addCleanup(td.cleanup);r=register(db,696,'john@ww.cx',{'fingerprint':'A'*40,'public_key_armored':'-----BEGIN PGP PUBLIC KEY BLOCK-----\nX\n-----END PGP PUBLIC KEY BLOCK-----','uids':['John <john@ww.cx>']});self.assertEqual(r['mode'],'sign_only');self.assertFalse(r['private_key_material_stored'])
 def test_wrong_contact_refused(self):
  td,db=self.db();self.addCleanup(td.cleanup)
  with self.assertRaises(RegistrationError): register(db,696,'wrong@ww.cx',{'fingerprint':'A'*40,'public_key_armored':'-----BEGIN PGP PUBLIC KEY BLOCK-----','uids':[]})
if __name__=='__main__':unittest.main()
