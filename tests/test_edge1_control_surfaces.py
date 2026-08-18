from __future__ import annotations

import json
import unittest
from pathlib import Path

from server.edge1_security_auth_http_config import HttpAdapterConfig

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/security/edge1-control-surfaces.json"
HTTP_CONFIG = ROOT / "config/security/edge1-security-auth-http.json"
CONSOLE = ROOT / "src/web/edge1-ops/control-surfaces/index.html"


class ControlSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.surfaces = {item["id"]: item for item in self.registry["surfaces"]}

    def test_registry_contract_and_unique_ids(self):
        self.assertEqual(self.registry["contract"], "wwcx.edge1-control-surfaces.v1")
        self.assertEqual(self.registry["status"], "staged_read_only")
        ids = [item["id"] for item in self.registry["surfaces"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(self.registry["principles"]["native_proxy_enabled"])
        self.assertTrue(self.registry["principles"]["private_controls_never_required_for_peering"])

    def test_private_controls_are_not_peering_dependencies(self):
        for item in self.registry["surfaces"]:
            if item["class"] == "private-control":
                self.assertEqual(item["peering_role"], "none", item["id"])
                self.assertFalse(str(item["wan_policy"]).startswith("allowed"), item["id"])

    def test_expected_public_and_peering_boundaries(self):
        self.assertEqual(self.surfaces["public-web"]["wan_policy"], "allowed")
        self.assertEqual(self.surfaces["wireguard"]["wan_policy"], "allowed")
        self.assertEqual(self.surfaces["public-ntp"]["wan_policy"], "allowed-ipv4")
        self.assertEqual(self.surfaces["kamailio-sip-current"]["wan_policy"], "blocked-pending-activation")
        self.assertEqual(self.surfaces["kamailio-sips-target"]["wan_policy"], "blocked-pending-activation")
        self.assertEqual(self.surfaces["rtp-media-range"]["wan_policy"], "blocked-pending-media-design")

    def test_asterisk_management_is_not_public_peering(self):
        for surface_id in ("asterisk-ami", "asterisk-http", "asterisk-https-wss"):
            item = self.surfaces[surface_id]
            self.assertEqual(item["class"], "private-control")
            self.assertEqual(item["peering_role"], "none")
        self.assertEqual(self.surfaces["asterisk-pjsip-backend"]["peering_role"], "backend-only")
        self.assertEqual(self.surfaces["asterisk-pjsip-backend"]["bind"], "loopback")

    def test_authenticated_http_contract_contains_exact_routes(self):
        config = HttpAdapterConfig.from_path(HTTP_CONFIG)
        self.assertEqual(config.routes["control_surfaces"], "/edge1-ops/control-surfaces/")
        self.assertEqual(config.routes["control_surfaces_registry"], "/edge1-ops/control-surfaces/registry.json")

    def test_console_is_read_only_and_nonce_compatible(self):
        source = CONSOLE.read_text(encoding="utf-8")
        self.assertEqual(source.count("<style>"), 1)
        self.assertEqual(source.count("<script>"), 1)
        self.assertNotIn("<form", source.lower())
        self.assertNotIn("fetch('/edge1-ops/api/", source)
        self.assertIn("disabled>Native broker not enabled", source)


if __name__ == "__main__":
    unittest.main()
