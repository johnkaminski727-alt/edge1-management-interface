#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import unittest
from unittest import mock

adapter = importlib.import_module("server.ava_contacts_gateway")


class AvaContactsGatewayTests(unittest.TestCase):
    def test_kind_and_limit_are_bounded(self):
        self.assertEqual(adapter.normalize_kind("Phones"), "phones")
        self.assertEqual(adapter.clamp_limit(1000), adapter.MAX_LIMIT)
        self.assertEqual(adapter.clamp_limit(0), 1)
        with self.assertRaises(adapter.AvaContactsError):
            adapter.normalize_kind("raw_sql")

    def test_empty_query_does_not_call_backend(self):
        with mock.patch.object(adapter, "signed_get") as signed:
            self.assertEqual(adapter.search_contacts("   "), [])
            signed.assert_not_called()

    def test_search_uses_signed_operations_api_and_sanitizes(self):
        raw = json.dumps([
            {
                "entity_id": 7,
                "entity_type": "organization",
                "canonical_name": "Example Co",
                "verification_status": "unverified",
                "assertion_id": 9,
                "confidence": "probable",
                "point_type": "phone",
                "normalized_value": "+13065550100",
                "display_value": "306-555-0100",
                "forbidden_secret": "must-not-pass",
            }
        ]).encode()

        with mock.patch.object(adapter, "credential_path", return_value=mock.sentinel.path), \
             mock.patch.object(adapter, "read_secret", return_value=b"x" * 32), \
             mock.patch.object(adapter, "signed_get", return_value=(200, raw)) as signed:
            rows = adapter.search_contacts("Example", kind="organizations", limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["confidence"], "probable")
        self.assertEqual(rows[0]["verification_status"], "unverified")
        self.assertNotIn("forbidden_secret", rows[0])
        self.assertEqual(rows[0]["source_name"], "Edge1 Unified Contacts")
        self.assertEqual(rows[0]["source_id"], "contact:assertion:9")
        args, kwargs = signed.call_args
        self.assertTrue(args[0].startswith("/v1/contacts/search?"))
        self.assertEqual(kwargs["actor"], "ava-contacts-gateway")

    def test_non_200_fails_closed(self):
        with mock.patch.object(adapter, "credential_path", return_value=mock.sentinel.path), \
             mock.patch.object(adapter, "read_secret", return_value=b"x" * 32), \
             mock.patch.object(adapter, "signed_get", return_value=(503, b'{"error":"unavailable"}')):
            with self.assertRaises(adapter.AvaContactsError):
                adapter.search_contacts("Example")


if __name__ == "__main__":
    unittest.main()
