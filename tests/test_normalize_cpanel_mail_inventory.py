from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import unittest

from tools.messaging import normalize_cpanel_mail_inventory as normalizer


DOMAINS = ["creekco.ca", "scgardens.ca", "omegafx.com"]


def uapi(data):
    return {
        "apiversion": 3,
        "module": "Email",
        "result": {
            "data": data,
            "errors": None,
            "messages": None,
            "metadata": {},
            "status": 1,
            "warnings": None,
        },
    }


class NormalizeCpanelMailInventoryTests(unittest.TestCase):
    def write_capture(self, root: pathlib.Path, *, filters=None) -> pathlib.Path:
        root.mkdir(parents=True)
        payloads = {
            "metadata.json": {
                "contract": "wwcx.cpanel-http-mail-inventory-evidence.v1",
                "captured_at": "2026-08-01T07:01:57Z",
                "read_only": True,
                "domains": DOMAINS,
                "transport": "https-cpanel-api-token",
                "sensitivity": "restricted-operational-metadata",
            },
            "list-mail-domains.json": uapi(DOMAINS),
            "list-pops.json": uapi(
                [
                    {
                        "email": "john@creekco.ca",
                        "domain": "creekco.ca",
                        "suspended_login": 0,
                        "suspended_incoming": 0,
                    },
                    {
                        "email": "records@scgardens.ca",
                        "domain": "scgardens.ca",
                        "suspended_login": 1,
                        "suspended_incoming": 1,
                    },
                ]
            ),
            "list-domain-forwarders.json": uapi([]),
            "list-filters.json": uapi(filters or []),
        }
        for domain in DOMAINS:
            safe = domain.replace(".", "_")
            payloads[f"list-forwarders-{safe}.json"] = uapi([])
            payloads[f"list-auto-responders-{safe}.json"] = uapi([])
            payloads[f"list-default-address-{safe}.json"] = uapi(
                {"domain": domain, "defaultaddress": ":fail:"}
            )
        payloads["list-forwarders-creekco_ca.json"] = uapi(
            [
                {
                    "address": "contact@creekco.ca",
                    "dest": "maildesk@ww.cx",
                }
            ]
        )

        lines = []
        for filename, payload in sorted(payloads.items()):
            path = root / filename
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {filename}")
        (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")
        return root

    def test_normalizes_mailboxes_forwarders_and_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(pathlib.Path(temp_dir) / "evidence")
            inventory = normalizer.normalize_capture(evidence)

        self.assertEqual(inventory["contract"], "wwcx.provider-mail-objects.v1")
        self.assertEqual(inventory["provider_family"], "namecheap_shared_hosting")
        self.assertEqual(len(inventory["default_addresses"]), 3)
        self.assertTrue(
            all(item["behavior"] == "reject" for item in inventory["default_addresses"])
        )
        self.assertTrue(
            all(item["mode"] == "unknown" for item in inventory["domain_routing"])
        )

        by_address = {}
        for item in inventory["objects"]:
            by_address.setdefault(item["address"], []).append(item)

        john = by_address["john@creekco.ca"][0]
        self.assertEqual(john["object_type"], "mailbox")
        self.assertEqual(john["access_class"], "private_john")
        self.assertTrue(john["active"])
        self.assertTrue(john["receives_mail"])
        self.assertFalse(john["can_send"])

        records = by_address["records@scgardens.ca"][0]
        self.assertEqual(records["access_class"], "shared_role")
        self.assertFalse(records["active"])
        self.assertFalse(records["receives_mail"])

        contact = by_address["contact@creekco.ca"][0]
        self.assertEqual(contact["object_type"], "forwarder")
        self.assertEqual(contact["destinations"], ["maildesk@ww.cx"])
        self.assertEqual(contact["access_class"], "shared_role")

    def test_rejects_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(pathlib.Path(temp_dir) / "evidence")
            (evidence / "list-pops.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(normalizer.CaptureError, "SHA-256 mismatch"):
                normalizer.normalize_capture(evidence)

    def test_rejects_behavior_that_requires_manual_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(
                pathlib.Path(temp_dir) / "evidence",
                filters=[{"filtername": "redirect"}],
            )
            with self.assertRaisesRegex(normalizer.CaptureError, "manual restricted review"):
                normalizer.normalize_capture(evidence)

    def test_rejects_incomplete_capture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = self.write_capture(pathlib.Path(temp_dir) / "evidence")
            missing = evidence / "list-forwarders-omegafx_com.json"
            missing.unlink()
            lines = [
                line
                for line in (evidence / "SHA256SUMS").read_text(encoding="ascii").splitlines()
                if not line.endswith("list-forwarders-omegafx_com.json")
            ]
            (evidence / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")
            with self.assertRaisesRegex(normalizer.CaptureError, "capture is incomplete"):
                normalizer.normalize_capture(evidence)


if __name__ == "__main__":
    unittest.main()
