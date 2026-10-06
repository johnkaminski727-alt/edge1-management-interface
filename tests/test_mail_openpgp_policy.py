import json
import pathlib
import unittest
from server import mail_openpgp_policy as module
ROOT = pathlib.Path(__file__).resolve().parents[1]
class TestOpenPGPPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT/'config/messaging/openpgp-policy.json').read_text())
    def test_safe_disabled_policy(self):
        self.assertFalse(module.validate_policy(self.policy)['enabled'])
    def test_required_encryption_without_key_fails(self):
        with self.assertRaises(module.OpenPGPPolicyError):
            module.resolve_mode(self.policy,'require_encryption',[],1)
    def test_opportunistic_missing_key_stays_plain(self):
        self.assertFalse(module.resolve_mode(self.policy,'encrypt_if_verified_key',[],1)['encrypt'])
    def test_verified_key_still_requires_activation(self):
        key = module.RecipientKey('a@example.test','A'*40,True)
        with self.assertRaises(module.OpenPGPPolicyError):
            module.resolve_mode(self.policy,'encrypt_if_verified_key',[key],1)
if __name__ == '__main__': unittest.main()
