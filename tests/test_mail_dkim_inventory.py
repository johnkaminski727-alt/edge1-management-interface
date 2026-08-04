from __future__ import annotations

import copy
import json
import pathlib
import tempfile
import unittest

from tools.messaging import mail_dkim_inventory as module


class MailDkimInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "contract": module.CANDIDATE_CONTRACT,
            "read_only": True,
            "domains": {
                "ww.cx": {
                    "provider_family": "namecheap_private_email",
                    "selection_status": "query_all_candidates",
                    "candidates": [
                        {
                            "selector": "default",
                            "basis": "synthetic legacy candidate",
                            "authoritative_for_activation": False,
                        },
                        {
                            "selector": "privateemail",
                            "basis": "synthetic current candidate",
                            "authoritative_for_activation": False,
                        },
                    ],
                }
            },
            "documentation_sources": [],
            "activation_boundary": {
                "dns_changes_authorized": False,
                "provider_login_authorized": False,
                "sender_activation_authorized": False,
                "delivery_authorized": False,
                "message_authorized": False,
            },
        }

    def test_normalizes_split_txt_chunks(self) -> None:
        value = '"v=DKIM1; k=rsa; p=ABC" "DEF123"'
        self.assertEqual(module.normalize_txt_data(value), "v=DKIM1; k=rsa; p=ABCDEF123")
        minimized = module.minimized_answer(value)
        self.assertTrue(minimized["record_shape_valid"])
        self.assertEqual(minimized["public_key_character_count"], 9)
        self.assertEqual(minimized["key_type"], "rsa")

    def test_builds_minimized_published_and_absent_results(self) -> None:
        def fake_query(resolver: str, url: str, query_name: str, timeout: float) -> dict:
            del url, timeout
            answers = []
            if query_name.startswith("default."):
                answers = ["v=DKIM1; k=rsa; p=ABCDEF123456"]
            return {
                "resolver": resolver,
                "status": "ok",
                "dns_status": 0,
                "authenticated_data": False,
                "answers": answers,
            }

        report = module.build_inventory(self.config, 5.0, query=fake_query)
        candidates = report["domains"]["ww.cx"]["candidates"]
        self.assertEqual(candidates[0]["analysis"]["state"], "published_valid_shape")
        self.assertEqual(candidates[1]["analysis"]["state"], "not_observed")
        self.assertEqual(
            report["summary"]["published_valid_shape_candidates"],
            [{"domain": "ww.cx", "selector": "default"}],
        )
        self.assertTrue(report["summary"]["dkim_dns_candidate_observed"])
        self.assertFalse(report["summary"]["provider_signing_verified"])
        self.assertFalse(report["summary"]["header_alignment_verified"])
        self.assertFalse(report["summary"]["ready_for_sender_activation"])
        self.assertNotIn("ABCDEF123456", json.dumps(report))

    def test_flags_resolver_disagreement(self) -> None:
        def fake_query(resolver: str, url: str, query_name: str, timeout: float) -> dict:
            del url, query_name, timeout
            answers = ["v=DKIM1; p=AAAA"] if resolver == "cloudflare" else []
            return {
                "resolver": resolver,
                "status": "ok",
                "dns_status": 0,
                "authenticated_data": False,
                "answers": answers,
            }

        report = module.build_inventory(self.config, 5.0, query=fake_query)
        for candidate in report["domains"]["ww.cx"]["candidates"]:
            self.assertEqual(candidate["analysis"]["state"], "resolver_disagreement")
            self.assertFalse(candidate["analysis"]["resolver_consensus"])

    def test_invalid_activation_candidate_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.config)
        invalid["domains"]["ww.cx"]["candidates"][0]["authoritative_for_activation"] = True
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "candidates.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(module.DkimInventoryError):
                module.load_candidates(path)

    def test_invalid_selector_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.config)
        invalid["domains"]["ww.cx"]["candidates"][0]["selector"] = "bad.selector"
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "candidates.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(module.DkimInventoryError):
                module.load_candidates(path)


if __name__ == "__main__":
    unittest.main()
