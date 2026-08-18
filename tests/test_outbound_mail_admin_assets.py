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
IDENTITIES = ROOT / "config" / "messaging" / "mail-identities.json"
ENGINE = ROOT / "server" / "outbound_mail_policy.py"
IDENTITY_ENGINE = ROOT / "server" / "mail_identity_registry.py"
IDENTITY_FACADE = ROOT / "server" / "identity_aware_outbound_gateway.py"


class OutboundMailAdminAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = HTML.read_text(encoding="utf-8")
        cls.js = JS.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.policy = POLICY.read_text(encoding="utf-8")
        cls.identities = IDENTITIES.read_text(encoding="utf-8")
        cls.engine = ENGINE.read_text(encoding="utf-8")
        cls.identity_engine = IDENTITY_ENGINE.read_text(encoding="utf-8")
        cls.identity_facade = IDENTITY_FACADE.read_text(encoding="utf-8")

    def test_required_assets_exist_and_are_nonempty(self) -> None:
        for path in (
            HTML,
            JS,
            CSS,
            DOC,
            POLICY,
            IDENTITIES,
            ENGINE,
            IDENTITY_ENGINE,
            IDENTITY_FACADE,
        ):
            with self.subTest(path=path):
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 100)

    def test_mail_room_keeps_all_major_views(self) -> None:
        for step in ("setup", "compose", "controls", "preview", "activity"):
            with self.subTest(step=step):
                self.assertIn(f'data-panel="{step}"', self.html)
                self.assertIn(f'data-step="{step}"', self.html)

    def test_daily_path_is_prominent_and_short(self) -> None:
        for token in (
            "Mail Room",
            "Today",
            "Write a message",
            "Review final message",
            "Find correspondence quickly",
            "The everyday path is intentionally simple",
        ):
            self.assertIn(token, self.html)
        self.assertIn('id="quick-compose"', self.html)
        self.assertIn('id="generate-preview"', self.html)
        self.assertIn("generatePreview", self.js)

    def test_preview_only_and_production_gate_are_visible(self) -> None:
        self.assertIn("Preview only", self.html)
        self.assertIn("live delivery is disabled", self.html)
        self.assertIn("explicit production authorization", self.html)
        self.assertIn('id="submit-message" disabled', self.html)

    def test_policy_controls_are_visible_but_not_fake_per_message_switches(self) -> None:
        self.assertIn("Policy-controlled", self.html)
        for token in (
            'id="include-action-link" type="checkbox" checked disabled',
            'id="include-disclosure" type="checkbox" checked disabled',
            'id="include-confidentiality" type="checkbox" checked disabled',
            'id="record-recipients" type="checkbox" checked disabled',
            'id="retention" disabled',
            'id="ip-mode" disabled',
        ):
            self.assertIn(token, self.html)

    def test_transparency_and_prohibited_controls_are_visible(self) -> None:
        self.assertIn("Disclose access logging", self.html)
        self.assertIn("Hidden open-tracking pixel", self.html)
        self.assertIn("Device fingerprinting", self.html)
        self.assertIn("Store full IP addresses", self.html)
        self.assertIn("does not create legal rights", self.html)
        self.assertIn("no-hidden-pixel", self.js)

    def test_automatic_sender_selection_is_visible_and_enforced(self) -> None:
        for token in (
            'id="original-recipient"',
            'id="system-generated"',
            "Submitted From and Reply-To values are not trusted",
            "john-inbox@ww.cx",
            "maildesk@ww.cx",
            "noreply@ww.cx",
        ):
            self.assertIn(token, self.html)
        for token in (
            "original_recipient",
            "identity_hint",
            "system_generated",
            "sender_selection",
            "managed_domains",
            "original_recipient_catch_all_proposal",
        ):
            self.assertIn(token, self.js + self.identity_facade)
        self.assertIn('"allow_submitted_from_override": false', self.identities)
        self.assertIn('"private_john_delivery_mailbox": "john-inbox@ww.cx"', self.identities)
        self.assertIn('"shared_role_delivery_mailbox": "maildesk@ww.cx"', self.identities)
        self.assertIn('"system_sender": "noreply@ww.cx"', self.identities)
        self.assertIn("submitted From override must remain disabled", self.identity_engine)
        self.assertIn('prepared["from_address"] = selection.address', self.identity_facade)

    def test_catch_all_preview_is_not_blocked_by_old_frontend_rule(self) -> None:
        self.assertIn("catch-all address can be preserved for review", self.js)
        self.assertIn("outside the managed Mail Room domains", self.js)
        self.assertNotIn("Original inbound recipient is not a registered sender identity.", self.js)

    def test_stale_preview_is_invalidated_after_message_edits(self) -> None:
        self.assertIn("function invalidatePreview()", self.js)
        self.assertIn("The message changed. Generate a fresh review before sending.", self.js)
        self.assertIn("$('#submit-message').disabled = true;", self.js)
        self.assertIn("state.preview = null", self.js)

    def test_draft_privacy_and_leave_protection_are_explicit(self) -> None:
        self.assertIn("Draft bodies are not saved to browser storage", self.html)
        self.assertIn("function hasDraftContent()", self.js)
        self.assertIn("beforeunload", self.js)
        self.assertIn("draftCommitted", self.js)

    def test_keyboard_shortcuts_do_not_disrupt_typing(self) -> None:
        self.assertIn("Mail Room shortcuts", self.html)
        self.assertIn("handleKeyboard", self.js)
        self.assertIn("const typing = isTypingTarget(event.target);", self.js)
        self.assertIn("event.key === 'Escape' && !typing", self.js)
        self.assertIn("event.metaKey || event.ctrlKey", self.js)
        self.assertIn("navigator.clipboard.writeText", self.js)
        self.assertIn("$('#quick-compose').addEventListener", self.js)

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

    def test_accessibility_and_responsive_layout_exist(self) -> None:
        self.assertIn("skip-link", self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("@media(max-width:1050px)", self.css)
        self.assertIn("@media(max-width:800px)", self.css)
        self.assertIn("@media(max-width:560px)", self.css)


if __name__ == "__main__":
    unittest.main()
