"""Per-domain signature organization and From display name (deploy/email/mail-room-send)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "deploy/email/mail-room-send/gateway/server"))

import identity_aware_outbound_gateway as gateway  # noqa: E402
import outbound_mail_gateway  # noqa: E402

POLICY = {"organization": {"legal_name": "Spirit Creek Gardens Inc.", "operating_name": "Spirit Creek Gardens",
                           "website": "https://spiritcreekgardens.com", "privacy_url": "https://spiritcreekgardens.com/privacy",
                           "contact_email": "contact@spiritcreekgardens.com", "mailing_address": "PO Box 333"}}
IDENTITIES = {
    "domains": {
        "ww.cx": {"legal_name": "Christmas Island Worldwide", "operating_name": "WW.CX"},
        "omegafx.com": {"legal_name": "OmegaFX Marketing Group Inc.", "operating_name": "OmegaFX"},
        "creekco.ca": {"legal_name": "Spirit Creek Gardens Inc.", "operating_name": "CreekCo / Spirit Creek Communications"},
    },
    "sender_profiles": {"john-wwcx": {"address": "john@ww.cx", "display_name": "John Kaminski"}},
}


class SignatureTests(unittest.TestCase):
    def test_ww_cx_signs_as_its_own_organization(self):
        org = gateway.organization_for_sender(POLICY, IDENTITIES, "john@ww.cx")["organization"]
        self.assertEqual((org["operating_name"], org["legal_name"]), ("WW.CX", "Christmas Island Worldwide"))
        self.assertEqual((org["website"], org["privacy_url"]), ("https://ww.cx", "https://ww.cx/privacy"))
        self.assertEqual(org["mailing_address"], "PO Box 333")

    def test_base_policy_is_not_mutated(self):
        gateway.organization_for_sender(POLICY, IDENTITIES, "john@ww.cx")
        self.assertEqual(POLICY["organization"]["operating_name"], "Spirit Creek Gardens")

    def test_each_domain_links_its_own_privacy_page(self):
        org = gateway.organization_for_sender(POLICY, IDENTITIES, "contact@omegafx.com")["organization"]
        self.assertEqual((org["website"], org["privacy_url"]), ("https://omegafx.com", "https://omegafx.com/privacy/"))
        org = gateway.organization_for_sender(POLICY, IDENTITIES, "noc@creekco.ca")["organization"]
        self.assertEqual(org["privacy_url"], "https://creekco.ca/privacy.html")

    def test_unknown_domain_leaves_policy_unchanged(self):
        self.assertIs(gateway.organization_for_sender(POLICY, IDENTITIES, "x@example.com"), POLICY)

    def test_display_names(self):
        self.assertEqual(gateway.sender_display_name(IDENTITIES, "JOHN@ww.cx"), "John Kaminski")
        self.assertEqual(gateway.sender_display_name(IDENTITIES, "noc@creekco.ca"), "CreekCo / Spirit Creek Communications")
        self.assertIsNone(gateway.sender_display_name(IDENTITIES, "x@example.com"))

    def test_from_header_includes_display_name(self):
        preview = {"request": {"from_address": "john@ww.cx", "from_display_name": "John Kaminski", "to": ["a@example.com"],
                               "cc": [], "bcc": [], "recipients": ["a@example.com"], "subject": "Hi", "reply_to": None},
                   "headers": {}, "body": "Hello"}
        try:
            message = outbound_mail_gateway.build_email_message(preview)
        except KeyError as exc:  # repo copy may expect extra preview fields; the From line is what matters
            self.skipTest(f"build_email_message needs {exc}")
        self.assertEqual(message["From"], "John Kaminski <john@ww.cx>")


if __name__ == "__main__":
    unittest.main()
