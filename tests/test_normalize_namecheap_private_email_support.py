from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import unittest

from tools.messaging import normalize_namecheap_private_email_support as normalizer


def base_evidence():
    return {
        "contract": "wwcx.namecheap-private-email-support-evidence.v1",
        "captured_at": "2026-08-01T18:00:00Z",
        "read_only": True,
        "provider_family": "namecheap_private_email",
        "domain": "ww.cx",
        "ticket_reference": "NC-JDV-2953",
        "subscription": {
            "status": "active",
            "plan": "Illustrative plan",
            "expiry_date": "2027-01-01",
            "mailbox_slots": 3,
        },
        "objects": [
            {
                "address": "john-inbox@ww.cx",
                "object_type": "mailbox",
                "destinations": [],
                "active": True,
                "receives_mail": True,
                "can_send": False,
                "quota_bytes": 1073741824,
                "notes": "Private delivery mailbox confirmed by provider.",
            },
            {
                "address": "maildesk@ww.cx",
                "object_type": "mailbox",
                "destinations": [],
                "active": True,
                "receives_mail": True,
                "can_send": False,
                "quota_bytes": 1073741824,
                "notes": "Shared role mailbox confirmed by provider.",
            },
            {
                "address": "john@ww.cx",
                "object_type": "alias",
                "destinations": ["john-inbox@ww.cx"],
                "active": True,
                "receives_mail": True,
                "can_send": True,
                "quota_bytes": None,
                "notes": "Alias sender capability explicitly confirmed.",
            },
            {
                "address": "noreply@ww.cx",
                "object_type": "system_account",
                "destinations": [],
                "active": True,
                "receives_mail": False,
                "can_send": True,
                "quota_bytes": None,
                "notes": "Outbound-only system sender.",
            },
        ],
        "catch_all": {
            "behavior": "reject",
            "destination": None,
        },
        "dkim": {
            "status": "enabled",
            "selector": "default",
        },
        "provider_rules": {
            "forwarding_reviewed": True,
            "filters_reviewed": True,
            "rules_present": False,
            "notes": "No provider-side rules observed.",
        },
        "completeness": {
            "subscription": True,
            "mailboxes": True,
            "aliases_and_groups": True,
            "catch_all": True,
            "quotas": True,
            "forwarding": True,
            "dkim": True,
            "sender_capability": True,
            "filters_and_rules": True,
        },
    }


class NormalizeNamecheapPrivateEmailSupportTests(unittest.TestCase):
    def write_bundle(
        self,
        root: pathlib.Path,
        *,
        evidence=None,
        include_source=True,
    ) -> pathlib.Path:
        root.mkdir(parents=True)
        payload = evidence or base_evidence()
        files = {
            "support-evidence.json": json.dumps(payload, indent=2) + "\n",
        }
        if include_source:
            files["NC-JDV-2953-response.txt"] = (
                "Restricted illustrative provider response retained outside Git.\n"
            )

        manifest = []
        for filename, content in sorted(files.items()):
            path = root / filename
            path.write_text(content, encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest.append(f"{digest}  {filename}")
        (root / "SHA256SUMS").write_text(
            "\n".join(manifest) + "\n",
            encoding="ascii",
        )
        return root

    def test_normalizes_objects_and_access_classes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = self.write_bundle(pathlib.Path(temp_dir) / "evidence")
            inventory, summary = normalizer.normalize_support_capture(evidence_dir)

        self.assertEqual(inventory["contract"], "wwcx.provider-mail-objects.v1")
        self.assertEqual(inventory["provider_family"], "namecheap_private_email")
        self.assertEqual(inventory["source"]["method"], "private_email_admin")
        self.assertEqual(inventory["source"]["account_reference"], "NC-JDV-2953")
        self.assertEqual(inventory["default_addresses"][0]["behavior"], "reject")
        self.assertEqual(inventory["domain_routing"], [])

        by_address = {item["address"]: item for item in inventory["objects"]}
        self.assertEqual(by_address["john-inbox@ww.cx"]["access_class"], "private_john")
        self.assertEqual(by_address["maildesk@ww.cx"]["access_class"], "shared_role")
        self.assertEqual(by_address["john@ww.cx"]["access_class"], "private_john")
        self.assertEqual(by_address["noreply@ww.cx"]["access_class"], "system")
        self.assertTrue(by_address["john@ww.cx"]["can_send"])
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["warnings"], [])
        self.assertEqual(summary["dkim"]["selector"], "default")

    def test_unknown_capabilities_fail_closed(self):
        evidence = base_evidence()
        evidence["objects"][0]["active"] = None
        evidence["objects"][0]["receives_mail"] = None
        evidence["objects"][0]["can_send"] = None
        evidence["completeness"]["sender_capability"] = False

        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = self.write_bundle(
                pathlib.Path(temp_dir) / "evidence",
                evidence=evidence,
            )
            inventory, summary = normalizer.normalize_support_capture(evidence_dir)

        john_inbox = next(
            item for item in inventory["objects"] if item["address"] == "john-inbox@ww.cx"
        )
        self.assertFalse(john_inbox["active"])
        self.assertFalse(john_inbox["receives_mail"])
        self.assertFalse(john_inbox["can_send"])
        self.assertIn("normalized to false", john_inbox["notes"])
        self.assertFalse(summary["complete"])
        self.assertTrue(
            any("sender capability" in warning for warning in summary["warnings"])
        )

    def test_rejects_secret_bearing_fields(self):
        evidence = base_evidence()
        evidence["support_pin"] = "not-allowed"
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = self.write_bundle(
                pathlib.Path(temp_dir) / "evidence",
                evidence=evidence,
            )
            with self.assertRaisesRegex(
                normalizer.SupportEvidenceError,
                "secret-bearing field",
            ):
                normalizer.normalize_support_capture(evidence_dir)

    def test_rejects_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = self.write_bundle(pathlib.Path(temp_dir) / "evidence")
            (evidence_dir / "support-evidence.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(
                normalizer.SupportEvidenceError,
                "SHA-256 mismatch",
            ):
                normalizer.normalize_support_capture(evidence_dir)

    def test_rejects_unmanifested_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = self.write_bundle(pathlib.Path(temp_dir) / "evidence")
            (evidence_dir / "loose-note.txt").write_text("unmanifested\n", encoding="utf-8")
            with self.assertRaisesRegex(
                normalizer.SupportEvidenceError,
                "unmanifested support evidence",
            ):
                normalizer.normalize_support_capture(evidence_dir)

    def test_rejects_object_outside_domain(self):
        evidence = base_evidence()
        evidence["objects"][0]["address"] = "john-inbox@example.com"
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = self.write_bundle(
                pathlib.Path(temp_dir) / "evidence",
                evidence=evidence,
            )
            with self.assertRaisesRegex(
                normalizer.SupportEvidenceError,
                "outside ww.cx",
            ):
                normalizer.normalize_support_capture(evidence_dir)

    def test_rejects_forward_catch_all_without_destination(self):
        evidence = base_evidence()
        evidence["catch_all"]["behavior"] = "forward"
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = self.write_bundle(
                pathlib.Path(temp_dir) / "evidence",
                evidence=evidence,
            )
            with self.assertRaisesRegex(
                normalizer.SupportEvidenceError,
                "requires a destination",
            ):
                normalizer.normalize_support_capture(evidence_dir)

    def test_provider_rules_and_incomplete_response_warn(self):
        evidence = base_evidence()
        evidence["provider_rules"]["rules_present"] = True
        evidence["provider_rules"]["filters_reviewed"] = False
        evidence["completeness"]["filters_and_rules"] = False
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = self.write_bundle(
                pathlib.Path(temp_dir) / "evidence",
                evidence=evidence,
            )
            _, summary = normalizer.normalize_support_capture(evidence_dir)

        self.assertFalse(summary["complete"])
        self.assertTrue(any("rules are present" in item for item in summary["warnings"]))
        self.assertTrue(any("incomplete" in item for item in summary["warnings"]))


if __name__ == "__main__":
    unittest.main()
