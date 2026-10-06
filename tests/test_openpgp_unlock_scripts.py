from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class TestOpenPGPUnlockScripts(unittest.TestCase):
    def test_preset_uses_stdin_not_passphrase_argument(self):
        text=(ROOT/'deploy/messaging/wwcx-openpgp-preset-passphrase.sh').read_text()
        self.assertIn('gpg-preset-passphrase',text)
        self.assertIn('--preset "$grip" < "$CRED"',text)
        self.assertNotIn('--passphrase',text)
        self.assertNotIn('-P "$',text)
    def test_installer_requires_encrypted_credential(self):
        text=(ROOT/'deploy/messaging/install-wwcx-openpgp-unlock.sh').read_text()
        self.assertIn('/etc/credstore.encrypted/wwcx-openpgp-passphrase.cred',text)
        self.assertIn('LoadCredentialEncrypted=',text)
        self.assertIn('ExecStartPre=',text)
if __name__=='__main__': unittest.main()
