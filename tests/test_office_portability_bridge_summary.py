import json
import unittest

from server.office_portability_bridge_summary import (
    DEFAULT_AVA_URL,
    DEFAULT_PORT_URL,
    build_summary,
)


class OfficePortabilityBridgeTests(unittest.TestCase):
    def test_unavailable_loopback_services_fail_closed(self):
        def unavailable(_url):
            raise OSError("loopback service unavailable")

        payload = build_summary(fetcher=unavailable)
        self.assertFalse(payload["ava_office"]["available"])
        self.assertFalse(payload["ava_office"]["execution_enabled"])
        self.assertFalse(payload["number_portability"]["available"])
        self.assertFalse(payload["number_portability"]["submission_authorized"])
        self.assertFalse(payload["number_portability"]["cutover_authorized"])

    def test_bridge_contains_only_sanitized_aggregate_fields(self):
        responses = {
            DEFAULT_AVA_URL: {
                "mode": "read-only",
                "work_items": {"new": 1, "completed": 3},
                "actions": {"blocked": 2},
                "standing_instructions": 4,
                "title": "Sensitive dentist appointment",
                "desired_outcome": "Call private clinic",
            },
            DEFAULT_PORT_URL: {
                "mode": "read-only",
                "cases": {"draft": 1},
                "numbers": 1,
                "documents": 1,
                "submission_authorized": False,
                "cutover_authorized": False,
                "customer_ref": "SECRET-CUSTOMER-REF",
                "number": "3065551212",
                "carrier": "Secret Carrier",
                "document_reference": "private/loa-secret.pdf",
            },
        }

        payload = build_summary(fetcher=lambda url: responses[url])
        encoded = json.dumps(payload, sort_keys=True)

        self.assertTrue(payload["ava_office"]["available"])
        self.assertEqual(payload["ava_office"]["work_items"].get("new"), 1)
        self.assertEqual(payload["ava_office"]["standing_instructions"], 4)
        self.assertFalse(payload["ava_office"]["execution_enabled"])
        self.assertTrue(payload["number_portability"]["available"])
        self.assertEqual(payload["number_portability"]["cases"].get("draft"), 1)
        self.assertEqual(payload["number_portability"]["numbers"], 1)
        self.assertEqual(payload["number_portability"]["documents"], 1)
        self.assertFalse(payload["number_portability"]["submission_authorized"])
        self.assertFalse(payload["number_portability"]["cutover_authorized"])
        self.assertFalse(payload["privacy"]["record_level_content_included"])

        for forbidden in (
            "Sensitive dentist appointment",
            "private clinic",
            "SECRET-CUSTOMER-REF",
            "3065551212",
            "Secret Carrier",
            "private/loa-secret.pdf",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_portability_authority_flags_cannot_be_promoted_by_source(self):
        responses = {
            DEFAULT_AVA_URL: {
                "mode": "read-only",
                "work_items": {},
                "actions": {},
                "standing_instructions": 0,
            },
            DEFAULT_PORT_URL: {
                "mode": "read-only",
                "cases": {},
                "numbers": 0,
                "documents": 0,
                "submission_authorized": True,
                "cutover_authorized": False,
            },
        }
        payload = build_summary(fetcher=lambda url: responses[url])
        self.assertFalse(payload["number_portability"]["available"])
        self.assertFalse(payload["number_portability"]["submission_authorized"])
        self.assertFalse(payload["number_portability"]["cutover_authorized"])

    def test_invalid_aggregate_values_fail_closed(self):
        responses = {
            DEFAULT_AVA_URL: {
                "mode": "read-only",
                "work_items": {"new": -1},
                "actions": {},
                "standing_instructions": 0,
            },
            DEFAULT_PORT_URL: {
                "mode": "read-only",
                "cases": {},
                "numbers": 0,
                "documents": 0,
                "submission_authorized": False,
                "cutover_authorized": False,
            },
        }
        payload = build_summary(fetcher=lambda url: responses[url])
        self.assertFalse(payload["ava_office"]["available"])
        self.assertFalse(payload["ava_office"]["execution_enabled"])


if __name__ == "__main__":
    unittest.main()
