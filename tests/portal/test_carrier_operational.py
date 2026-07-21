#!/usr/bin/env python3

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "portal"))

from carrier_operational import (  # noqa: E402
    PortalIdentity,
    carrier_scope,
    identity_from_config,
    operational_response,
)


class CarrierOperationalTests(unittest.TestCase):
    def test_identity_defaults_to_read_only_scopes(self):
        identity = identity_from_config(
            "carrier-a-client",
            {"secret": "not-used-in-this-test", "carrier_id": "carrier-a"},
        )

        self.assertEqual(identity.client_id, "carrier-a-client")
        self.assertEqual(identity.carrier_id, "carrier-a")
        self.assertTrue(identity.permits("/portal/carrier/profile"))
        self.assertTrue(identity.permits("/portal/carrier/interconnects"))

    def test_explicit_scopes_are_enforced(self):
        identity = identity_from_config(
            "limited-client",
            {
                "carrier_id": "carrier-a",
                "scopes": ["carrier.profile.read"],
            },
        )

        self.assertTrue(identity.permits("/portal/carrier/profile"))
        self.assertFalse(identity.permits("/portal/carrier/metrics"))

    def test_carrier_scope_filters_cross_tenant_records(self):
        payload = {
            "interconnects": [
                {"carrier_id": "carrier-a", "name": "a-primary"},
                {"carrier_id": "carrier-b", "name": "b-primary"},
            ],
            "generated_at": "2026-07-21T00:00:00Z",
        }

        scoped = carrier_scope(payload, "carrier-a")

        self.assertEqual(scoped["carrier_id"], "carrier-a")
        self.assertEqual(
            scoped["interconnects"],
            [{"carrier_id": "carrier-a", "name": "a-primary"}],
        )

    def test_carrier_scope_removes_sensitive_fields(self):
        payload = {
            "carrier_id": "carrier-a",
            "name": "Carrier A",
            "secret": "remove-me",
            "technical": {
                "management_ip": "192.0.2.10",
                "status": "healthy",
            },
        }

        scoped = carrier_scope(payload, "carrier-a")

        self.assertNotIn("secret", scoped)
        self.assertNotIn("management_ip", scoped["technical"])
        self.assertEqual(scoped["technical"]["status"], "healthy")

    def test_carrier_identity_is_required(self):
        with self.assertRaises(PermissionError):
            carrier_scope([], None)

    def test_operational_response_reads_and_filters_export(self):
        identity = PortalIdentity(
            client_id="carrier-a-client",
            carrier_id="carrier-a",
            scopes=frozenset({"carrier.interconnect.read"}),
        )

        with tempfile.TemporaryDirectory() as directory:
            portal_dir = Path(directory)
            (portal_dir / "interconnect-status.json").write_text(
                json.dumps(
                    {
                        "interconnects": [
                            {"carrier_id": "carrier-a", "status": "healthy"},
                            {"carrier_id": "carrier-b", "status": "degraded"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            response = operational_response(
                portal_dir,
                "/portal/carrier/interconnects",
                identity,
            )

        self.assertEqual(
            response["interconnects"],
            [{"carrier_id": "carrier-a", "status": "healthy"}],
        )

    def test_operational_response_rejects_missing_scope(self):
        identity = PortalIdentity(
            client_id="carrier-a-client",
            carrier_id="carrier-a",
            scopes=frozenset(),
        )

        with self.assertRaises(PermissionError):
            operational_response(
                Path("unused"),
                "/portal/carrier/metrics",
                identity,
            )


if __name__ == "__main__":
    unittest.main()
