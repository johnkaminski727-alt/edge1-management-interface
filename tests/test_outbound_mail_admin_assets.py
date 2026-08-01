#!/usr/bin/env python3

from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = ROOT / "src" / "web" / "outbound-mail" / "index.html"
JS = ROOT / "src" / "web" / "outbound-mail" / "app.js"
CSS = ROOT / "src" / "web" / "outbound-mail" / "styles.css"
DOC = ROOT / "docs" / "messaging" / "outbound-mail-compliance-gateway.md"
POLICY = ROOT / "config" / "messaging" / "outbound-mail-policy.json"
ENGINE = ROOT / "server" / "outbound_mail_policy.py"


class OutboundMailAdminAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = HTML.read_text(encoding="utf-8")
        cls.js = JS.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.policy = POLICY.read_text(encoding="utf-8")
        cls.engine = ENGINE.read_text(encoding="utf-8")

    def test_required_assets_exist_and_are_nonempty(self) -> None:
        for path in (HTML, JS, CSS, DOC, POLICY, ENGINE):
            with self.subTest(path=path):
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 100)

    def test_admin_flow_contains_all_major_steps(self) -> None:
        for step in ("setup", "compose", "controls", "preview", "activity"):
            with self.subTest(step=step):
                self.assertIn(f'data-panel="{step}"', self.html)
                self.assertIn(f'data-step="{step}"', self.html)

    def test_preview_only_and_production_gate_are_visible(self) -> None:
        self.assertIn("Preview only", self.html)
        self.assertIn("live delivery is disabled", self.html)
        self.assertIn("explicit production authorization", self.html)
        self.assertIn('id="submit-message" disabled', self.html)

    def test_transparency_and_prohibited_controls_are_visible(self) -> None:
        self.assertIn("Disclose access logging", self.html)
        self.assertIn("Hidden open-tracking pixel", self.html)
        self.assertIn("Device fingerprinting", self.html)
        self.assertIn("Store full IP addresses", self.html)
        self.assertIn("does not create legal rights", self.html)
        self.assertIn("no-hidden-pixel", self.js)

    def test_chatgpt_and_provider_abstraction_are_documented(self) -> None:
        self.assertIn("ChatGPT and automation path", self.doc)
        self.assertIn("Delivery adapters", self.doc)
        self.assertIn("authenticated SMTP smarthost", self.doc)
        self.assertIn("provider-independent-request-id", self.doc)

    def test_policy_engine_rejects_covert_tracking(self) -> None:
        self.assertIn("hidden open tracking is prohibited", self.engine)
        self.assertIn("device fingerprinting is prohibited", self.engine)
        self.assertIn("full IP-address storage is prohibited", self.engine)
        self.assertIn('"hidden_open_tracking": false', self.policy)
        self.assertIn('"device_fingerprinting": false', self.policy)
        self.assertIn('"collect_full_ip": false', self.policy)

    def test_mobile_layout_exists(self) -> None:
        self.assertIn("@media(max-width:900px)", self.css)
        self.assertIn("@media(max-width:560px)", self.css)


if __name__ == "__main__":
    unittest.main()
