import pathlib,sqlite3,tempfile,unittest
from server.unified_contacts import UnifiedContacts
from tools.unified_contacts.schema_openpgp import apply_schema

class OpenPGPReadModelTests(unittest.TestCase):
    def test_evidence_exposes_public_metadata_not_armored_key(self):
        with tempfile.TemporaryDirectory() as td:
            db=pathlib.Path(td)/'contacts.sqlite'
            con=sqlite3.connect(db)
            con.executescript('''
            create table contact_entities(id integer primary key,entity_type text,canonical_name text,display_name text,lifecycle_status text,verification_status text);
            create table contact_points(id integer primary key,point_type text,normalized_value text,display_value text,lifecycle_status text,legacy_phone_number_id integer);
            create table contact_assertions(id integer primary key,entity_id integer,contact_point_id integer,valid_from text,valid_to text,confidence text,assertion_type text,notes text);
            create table assertion_evidence(id integer primary key,assertion_id integer,provenance_id integer,evidence_role text,evidence_summary text);
            create table provenance_records(id integer primary key,source_document_id text,source_kind text,source_name text,source_reference text,source_page text,source_url text,source_sha256 text,extraction_method text,verification_status text,notes text);
            create table contact_entity_aliases(id integer primary key,entity_id integer,alias_name text,alias_type text,confidence text,provenance_id integer,source_path text,notes text);
            create table contact_attestations(id integer primary key,entity_id integer,contact_point_id integer,provenance_id integer,attribute text,attested_value text,classification text,verification_status text,source_path text,notes text);
            create table contact_observations(id integer primary key,contact_point_id integer,provenance_id integer,observation_type text,observed_value text,occurred_at text,direction text,classification text,confidence text,notes text);
            ''')
            apply_schema(con)
            con.execute("insert into contact_entities values(1,'person','John','John','active','verified')")
            con.execute("insert into contact_points values(696,'email','john@ww.cx','john@ww.cx','active',null)")
            con.execute("insert into contact_assertions(id,entity_id,contact_point_id,confidence,assertion_type) values(1,1,696,'confirmed','email')")
            con.execute("insert into contact_openpgp_keys(contact_point_id,fingerprint,public_key_armored,verification_status,source) values(696,?,'-----BEGIN PGP PUBLIC KEY BLOCK-----','verified','commissioning')",('A'*40,))
            con.execute("insert into contact_openpgp_policy(contact_point_id,mode) values(696,'sign_only')")
            con.commit(); con.close()
            detail=UnifiedContacts(str(db)).evidence(entity_id=1,limit=250)
            self.assertEqual(detail['openpgp_keys'][0]['fingerprint'],'A'*40)
            self.assertEqual(detail['openpgp_policies'][0]['mode'],'sign_only')
            self.assertNotIn('public_key_armored',detail['openpgp_keys'][0])

if __name__=='__main__': unittest.main()
