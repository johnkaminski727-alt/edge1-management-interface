import json
import pathlib
import sys
import unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"server"))
import mail_local_mta as local
import mail_identity_registry as identities
import outbound_mail_gateway as gateway
class LocalMTATests(unittest.TestCase):
    def test_other_domain_blocked_before_socket(self):
        c={"provider":{"selected":"edge1","profiles":{"edge1":{"type":"local_mta","enabled":True,"allowed_from_domains":["spiritcreekgardens.com"]}}}}
        with patch.object(local.smtplib,"SMTP") as smtp:
            with self.assertRaises(gateway.ProviderUnavailableError):
                local.submit(c,{"request":{"from_address":"john@ww.cx","recipients":["test@example.com"]}},b"test","test")
            smtp.assert_not_called()
    def test_scan_unavailable_raises(self):
        with patch.object(local.socket,"socket",side_effect=OSError("unavailable")):
            with self.assertRaises(OSError): local.scan(b"test")
    def test_catchall_activation_scoped_to_contact_gate(self):
        r=json.loads((ROOT/"config/messaging/mail-identities.json").read_text())
        r["catch_all_domains"]={"spiritcreekgardens.com":{"default_sender":"contact@spiritcreekgardens.com","delivery_mailbox":"maildesk@ww.cx"}}
        r["outbound_activation_authorized"]=True
        r["sender_selection"]["live_sender_allowlist"]=["contact@spiritcreekgardens.com"]
        self.assertTrue(identities.resolve_sender(r,{"original_recipient":"arbitrary@spiritcreekgardens.com"}).live_enabled)
        self.assertFalse(identities.resolve_sender(r,{"original_recipient":"john@ww.cx"}).live_enabled)
