import json
from pathlib import Path
import tempfile
import unittest

from server.ava_office_manager import OfficeManagerStore
from server.number_portability_center import PortabilityStore
from server.office_portability_bridge_summary import build_summary


class OfficePortabilityBridgeTests(unittest.TestCase):
    def test_missing_databases_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = build_summary(root / "missing-ava.sqlite3", root / "missing-port.sqlite3")
        self.assertFalse(payload["ava_office"]["available"])
        self.assertFalse(payload["ava_office"]["execution_enabled"])
        self.assertFalse(payload["number_portability"]["available"])
        self.assertFalse(payload["number_portability"]["submission_authorized"])
        self.assertFalse(payload["number_portability"]["cutover_authorized"])

    def test_bridge_contains_counts_not_record_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ava_path = root / "ava.sqlite3"
            port_path = root / "port.sqlite3"

            office = OfficeManagerStore(ava_path)
            office.create_work_item(
                title="Sensitive dentist appointment",
                desired_outcome="Call private clinic and arrange appointment",
                source_channel="phone",
                source_ref="call-secret-ref",
            )
            office.add_standing_instruction(
                domain="calendar.event.create",
                statement="Prefer private afternoons",
                effect="prefer",
            )

            ports = PortabilityStore(port_path)
            case = ports.create_case(
                direction="inbound",
                customer_ref="SECRET-CUSTOMER-REF",
                numbers=["3065551212"],
                losing_carrier="Secret Carrier",
            )
            ports.add_document(
                case["id"],
                document_type="loa",
                reference="private/loa-secret.pdf",
            )

            payload = build_summary(ava_path, port_path)
            encoded = json.dumps(payload, sort_keys=True)

        self.assertTrue(payload["ava_office"]["available"])
        self.assertEqual(payload["ava_office"]["work_items"].get("new"), 1)
        self.assertEqual(payload["ava_office"]["standing_instructions"], 1)
        self.assertTrue(payload["number_portability"]["available"])
        self.assertEqual(payload["number_portability"]["cases"].get("draft"), 1)
        self.assertEqual(payload["number_portability"]["numbers"], 1)
        self.assertEqual(payload["number_portability"]["documents"], 1)
        self.assertFalse(payload["privacy"]["record_level_content_included"])

        for forbidden in (
            "Sensitive dentist appointment",
            "private clinic",
            "call-secret-ref",
            "Prefer private afternoons",
            "SECRET-CUSTOMER-REF",
            "3065551212",
            "Secret Carrier",
            "private/loa-secret.pdf",
        ):
            self.assertNotIn(forbidden, encoded)


if __name__ == "__main__":
    unittest.main()
