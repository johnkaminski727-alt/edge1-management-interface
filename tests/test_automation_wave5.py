import importlib.util, sqlite3, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
account=load('accounting_wave5','tools/automation/accounting_intake_bot.py')
cred=load('credential_wave5','tools/automation/credential_lifecycle_bot.py')
class Wave5Tests(unittest.TestCase):
    def test_accounting_schema_has_no_payment_authority(self):
        self.assertIn('accounting_items',account.SCHEMA)
        src=(ROOT/'tools/automation/accounting_intake_bot.py').read_text()
        self.assertIn("'payment_authorized':False",src)
        self.assertIn("'bank_mutation_authorized':False",src)
    def test_credential_bot_never_reads_file_contents(self):
        src=(ROOT/'tools/automation/credential_lifecycle_bot.py').read_text()
        self.assertNotIn('.read_text(',src)
        self.assertNotIn('open(',src)
        self.assertIn("'credential_contents_read':False",src)
    def test_mail_learning_cannot_release_quarantine(self):
        src=(ROOT/'tools/automation/mail_learning_intelligence_bot.py').read_text()
        self.assertIn("'quarantine_release_authorized':False",src)
        self.assertIn("'thresholds_changed':False",src)
    def test_ava_quality_preserves_recent_and_historical_windows(self):
        src=(ROOT/'tools/automation/ava_quality_control_bot.py').read_text()
        self.assertIn("'recent_hours'",src)
        self.assertIn("'recent_metrics'",src)
        self.assertIn("'historical_recommendations'",src)
    def test_ava_quality_is_metadata_only(self):
        src=(ROOT/'tools/automation/ava_quality_control_bot.py').read_text()
        for token in ("'content_included':False","'user_identifiers_included':False","'request_identifiers_included':False","'mutation_performed':False"):
            self.assertIn(token,src)
    def test_units_and_installer_exist(self):
        for name in ('edge1-accounting-intake','edge1-mail-learning','edge1-credential-lifecycle','edge1-ava-quality-control'):
            self.assertTrue((ROOT/f'deploy/automation-wave5/{name}.service').is_file())
            self.assertTrue((ROOT/f'deploy/automation-wave5/{name}.timer').is_file())
if __name__=='__main__': unittest.main()
