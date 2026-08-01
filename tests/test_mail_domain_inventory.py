#!/usr/bin/env python3

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "messaging"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mail_domain_inventory as MODULE


class MailDomainInventoryTests(unittest.TestCase):
    def test_managed_domain_set_is_exact(self) -> None:
        self.assertEqual(
            set(MODULE.DOMAINS),
            {
                "ww.cx",
                "creekco.ca",
                "spiritcreekgardens.com",
                "scgardens.ca",
                "omegafx.com",
            },
        )

    def test_record_normalization(self) -> None:
        self.assertEqual(
            MODULE._normalize_record_data("MX", "10 ASPMX.L.GOOGLE.COM."),
            "10 aspmx.l.google.com",
        )
        self.assertEqual(
            MODULE._normalize_record_data("NS", "NS1.EXAMPLE.COM."),
            "ns1.example.com",
        )
        self.assertEqual(
            MODULE._normalize_record_data("TXT", '"v=spf1 include:_spf.google.com ~all"'),
            "v=spf1 include:_spf.google.com ~all",
        )

    def test_consensus_preserves_disagreement(self) -> None:
        result = MODULE.consensus(
            [
                {"status": "ok", "answers": ["10 mx1.example"]},
                {"status": "ok", "answers": ["20 mx2.example"]},
            ]
        )
        self.assertFalse(result["agreed"])
        self.assertEqual(
            result["answers"],
            ["10 mx1.example", "20 mx2.example"],
        )

    def test_provider_inference(self) -> None:
        cases = {
            "google_workspace": ["1 aspmx.l.google.com"],
            "microsoft_365": ["0 tenant.mail.protection.outlook.com"],
            "namecheap_private_email": ["10 mx1.privateemail.com"],
            "namecheap_shared_hosting": ["5 mx1-hosting.jellyfish.systems"],
            "cloudflare_email_routing": ["10 route1.mx.cloudflare.net"],
            "zoho_mail": ["10 mx.zoho.com"],
            "no_published_mx_observed": [],
        }
        for expected, records in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(
                    MODULE.infer_mail_provider(records)["provider_family"],
                    expected,
                )

    def test_inventory_shape_without_network(self) -> None:
        original = MODULE.query_resolver
        try:
            MODULE.query_resolver = lambda resolver_name, resolver_url, name, record_type, timeout: {
                "resolver": resolver_name,
                "status": "ok",
                "dns_status": 0,
                "authenticated_data": False,
                "answers": [],
            }
            inventory = MODULE.build_inventory(1.0)
        finally:
            MODULE.query_resolver = original
        self.assertTrue(inventory["read_only"])
        self.assertEqual(inventory["contract"], "wwcx.mail-domain-dns-inventory.v1")
        self.assertEqual(set(inventory["domains"]), set(MODULE.DOMAINS))
        for domain in inventory["domains"].values():
            self.assertEqual(
                set(domain["records"]),
                {"mx", "spf_txt", "dmarc_txt", "ns"},
            )


if __name__ == "__main__":
    unittest.main()
