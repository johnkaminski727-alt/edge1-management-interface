import pathlib,sqlite3,tempfile,unittest
from tools.messaging.publish_openpgp_public_key import publish,PublishError
from tools.unified_contacts.schema_openpgp import apply_schema
class TestPublisher(unittest.TestCase):
 def fixture(self,armor='-----BEGIN PGP PUBLIC KEY BLOCK-----\nabc\n-----END PGP PUBLIC KEY BLOCK-----'):
  td=tempfile.TemporaryDirectory(); root=pathlib.Path(td.name); db=root/'c.sqlite'; con=sqlite3.connect(db)
  con.execute('create table contact_points(id integer primary key,normalized_value text)'); con.execute("insert into contact_points values(696,'john@ww.cx')"); apply_schema(con)
  con.execute("insert into contact_openpgp_keys(contact_point_id,fingerprint,public_key_armored,verification_status,source) values(696,?,?, 'verified','commissioning')",('A'*40,armor));con.commit();con.close();return td,db,root/'out'
 def test_publishes_public_only(self):
  td,db,out=self.fixture(); self.addCleanup(td.cleanup); meta=publish(db,696,out,'john-wwcx'); self.assertFalse(meta['private_key_material_included']); self.assertIn('PUBLIC KEY',(out/'john-wwcx.asc').read_text())
 def test_schema_rejects_private_material(self):
  with tempfile.TemporaryDirectory() as td:
   db=pathlib.Path(td)/'c.sqlite'; con=sqlite3.connect(db)
   con.execute('create table contact_points(id integer primary key,normalized_value text)')
   con.execute("insert into contact_points values(696,'john@ww.cx')"); apply_schema(con)
   with self.assertRaises(sqlite3.IntegrityError):
    con.execute("insert into contact_openpgp_keys(contact_point_id,fingerprint,public_key_armored,verification_status,source) values(696,?,?, 'verified','commissioning')",('A'*40,'-----BEGIN PGP PRIVATE KEY BLOCK-----'))
   con.close()
 def test_non_public_material_refused(self):
  td,db,out=self.fixture('not a public key'); self.addCleanup(td.cleanup)
  with self.assertRaises(PublishError): publish(db,696,out,'john-wwcx')
if __name__=='__main__':unittest.main()
