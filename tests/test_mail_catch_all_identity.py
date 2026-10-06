import copy
import json
import pathlib
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import mail_identity_registry as m
class CatchAllTests(unittest.TestCase):
    def setUp(self):
        self.r=json.loads((ROOT / "config/messaging/mail-identities.json").read_text())
        self.r["catch_all_domains"]={"spiritcreekgardens.com":{"default_sender":"contact@spiritcreekgardens.com","delivery_mailbox":self.r["mailboxes"]["shared_role"]["address"]}}
    def test_original_and_contact_reply_choices(self):
        for hint,want in [("","new-alias@spiritcreekgardens.com"),("contact@spiritcreekgardens.com","contact@spiritcreekgardens.com")]:
            x=m.resolve_sender(self.r,{"original_recipient":"new-alias@spiritcreekgardens.com","identity_hint":hint,"from_address":"spoof@example.com"})
            self.assertEqual(x.address,want)
            self.assertFalse(x.live_enabled)
            self.assertTrue(x.from_address_replaced)
    def test_new_domain_message_uses_contact(self):
        self.assertEqual(m.resolve_sender(self.r,{"identity_hint":"spiritcreekgardens.com"}).address,"contact@spiritcreekgardens.com")
    def test_cross_domain_reply_and_unmanaged_address_rejected(self):
        for payload in [{"original_recipient":"unknown@outside.example"},{"original_recipient":"new@spiritcreekgardens.com","identity_hint":"john@ww.cx"}]:
            with self.assertRaises(m.IdentitySelectionError):m.resolve_sender(self.r,payload)
    def test_wwcx_private_sender_preserved(self):
        self.assertEqual(m.resolve_sender(self.r,{"original_recipient":"john@ww.cx"}).address,"john@ww.cx")
    def test_invalid_domain_or_mailbox_rejected(self):
        for value in [{"outside.example":{"default_sender":"contact@outside.example","delivery_mailbox":"maildesk@ww.cx"}},{"spiritcreekgardens.com":{"default_sender":"contact@spiritcreekgardens.com","delivery_mailbox":"john-inbox@ww.cx"}}]:
            r=copy.deepcopy(self.r);r["catch_all_domains"]=value
            with self.assertRaises(m.IdentityConfigurationError):m.validate_registry(r)
