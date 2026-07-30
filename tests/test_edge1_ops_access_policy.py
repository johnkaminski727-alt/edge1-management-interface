#!/usr/bin/env python3
"""Policy, authorization, privacy, and static boundary tests for /edge1-ops/."""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "edge1_ops_access_policy.py"
POLICY_PATH = ROOT / "config" / "security" / "edge1-authenticated-operations-policy.json"
SCHEMA_PATH = ROOT / "schemas" / "wwcx-edge1-authenticated-operations-policy-v1.schema.json"
APACHE_PATH = ROOT / "deploy" / "apache" / "edge1-ops-authenticated.conf.design"

SPEC = importlib.util.spec_from_file_location("edge1_ops_access_policy", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Edge1OpsAccessPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.source = MODULE_PATH.read_text(encoding="utf-8")
        cls.apache = APACHE_PATH.read_text(encoding="utf-8")
        cls.now = 2_000_000_000

    def valid_identity(self, scopes=None):
        granted = [MODULE.GENERAL_SCOPE] if scopes is None else list(scopes)
        return {
            "authenticated": True,
            "subject": "operator-123",
            "issuer_trusted": True,
            "audience_valid": True,
            "mfa": True,
            "session_identifier_hash": "a" * 64,
            "issued_at": self.now - 3600,
            "last_seen_at": self.now - 60,
            "expires_at": self.now + 3600,
            "scopes": granted,
            "raw_token": "must-not-propagate",
            "cookie": "must-not-propagate",
            "email": "operator@example.invalid",
            "query": "token=must-not-propagate",
        }

    def authorize(self, path, identity=None, method="GET"):
        return MODULE.authorize_request(
            self.policy,
            method,
            path,
            identity,
            now_epoch=self.now,
        )

    def test_committed_policy_is_disabled_and_schema_contract_matches(self) -> None:
        MODULE.validate_policy(self.policy)
        self.assertEqual(self.policy["contract"], MODULE.CONTRACT)
        self.assertEqual(self.schema["properties"]["contract"]["const"], MODULE.CONTRACT)
        for key in (
            "enabled",
            "deployment_authorized",
            "authentication_change_authorized",
            "live_route_authorized",
            "anonymous_fallback",
        ):
            self.assertIs(self.policy[key], False)
        self.assertIs(self.policy["provider"]["identity_provider_selected"], False)
        self.assertIs(self.policy["provider"]["adapter_inventory_verified"], False)
        self.assertIs(self.policy["acceptance"]["live_change_authorized"], False)

    def test_policy_rejects_security_contract_drift(self) -> None:
        mutations = (
            lambda value: value.update(anonymous_fallback=True),
            lambda value: value.update(unexpected="field"),
            lambda value: value["provider"].update(refresh_tokens_allowed=True),
            lambda value: value["provider"].update(raw_token_storage_allowed=True),
            lambda value: value["provider"].update(pkce_method="plain"),
            lambda value: value["session"]["cookie"].update(secure=False),
            lambda value: value["session"]["cookie"].update(http_only=False),
            lambda value: value["session"]["cookie"].update(same_site="Lax"),
            lambda value: value["session"]["cookie"].update(domain="edge1.ww.cx"),
            lambda value: value["request_boundary"].update(unauthenticated_api_status=302),
            lambda value: value["request_boundary"].update(api_redirect_on_auth_failure=True),
            lambda value: value["response_headers"].update(cors_allow_origin="*"),
            lambda value: value["audit"].update(tokens_recorded=True),
            lambda value: value["route_rules"][0].update(path="/edge1-status/security/"),
            lambda value: value["route_rules"][0].update(required_scopes=[MODULE.GENERAL_SCOPE]),
        )
        for mutate in mutations:
            value = copy.deepcopy(self.policy)
            mutate(value)
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    MODULE.validate_policy(value)

    def test_partial_or_unverified_activation_is_rejected(self) -> None:
        partial = copy.deepcopy(self.policy)
        partial["enabled"] = True
        with self.assertRaises(ValueError):
            MODULE.validate_policy(partial)

        unverified = copy.deepcopy(self.policy)
        for key in (
            "enabled",
            "deployment_authorized",
            "authentication_change_authorized",
            "live_route_authorized",
        ):
            unverified[key] = True
        with self.assertRaises(ValueError):
            MODULE.validate_policy(unverified)

    def test_unknown_and_ambiguous_paths_are_404_before_auth(self) -> None:
        paths = (
            "/edge1-ops/not-registered",
            "/edge1-status/",
            "/edge1-ops/security/../reports/",
            "/edge1-ops/security/%2e%2e/reports/",
            "/edge1-ops/security//history/",
            "/edge1-ops/security/history/?token=secret",
            "/edge1-ops/security\\history/",
            "/edge1-ops/\x00security/",
            "/edge1-ops/api/v1/security/suricata/historyevil",
        )
        for path in paths:
            with self.subTest(path=path):
                decision = self.authorize(path)
                self.assertIs(decision["allowed"], False)
                self.assertEqual(decision["status"], 404)
                self.assertEqual(decision["reason"], "not_found")
                self.assertEqual(decision["classification"], "unknown")

    def test_known_route_requires_valid_authenticated_session(self) -> None:
        missing = self.authorize("/edge1-ops/security/")
        self.assertEqual(missing["status"], 401)
        self.assertEqual(missing["reason"], "identity_unresolved")

        invalid_cases = (
            {"issuer_trusted": False},
            {"audience_valid": False},
            {"mfa": False},
            {"expires_at": self.now},
            {"last_seen_at": self.now - 901},
            {"issued_at": self.now - 28801},
            {"session_identifier_hash": "raw-session-id"},
        )
        for updates in invalid_cases:
            identity = self.valid_identity()
            identity.update(updates)
            with self.subTest(updates=updates):
                denied = self.authorize("/edge1-ops/security/", identity)
                self.assertEqual(denied["status"], 401)
                self.assertIs(denied["allowed"], False)

    def test_general_scope_allows_only_registered_read_routes(self) -> None:
        identity = self.valid_identity()
        paths = (
            "/edge1-ops/",
            "/edge1-ops/security/",
            "/edge1-ops/security/alerts/123",
            "/edge1-ops/network-defense/",
            "/edge1-ops/bitcoin/",
            "/edge1-ops/mining/",
            "/edge1-ops/reports/",
            "/edge1-ops/data/operations-health.json",
        )
        for path in paths:
            with self.subTest(path=path):
                decision = self.authorize(path, identity)
                self.assertIs(decision["allowed"], True)
                self.assertEqual(decision["status"], 200)
                self.assertIn(MODULE.GENERAL_SCOPE, decision["required_scopes"])

    def test_scope_and_method_failures_are_distinct(self) -> None:
        forbidden = self.authorize(
            "/edge1-ops/network-defense/",
            self.valid_identity(scopes=[]),
        )
        self.assertEqual(forbidden["status"], 403)
        self.assertEqual(forbidden["reason"], "scope_missing")

        method = self.authorize(
            "/edge1-ops/network-defense/",
            self.valid_identity(),
            method="POST",
        )
        self.assertEqual(method["status"], 405)
        self.assertEqual(method["reason"], "method_not_allowed")

    def test_history_requires_both_scopes_and_history_rate_limit(self) -> None:
        paths = (
            "/edge1-ops/security/history/",
            "/edge1-ops/security/history/events/abc",
            "/edge1-ops/api/v1/security/suricata/history",
            "/edge1-ops/api/v1/security/suricata/history/events/abc",
        )
        for path in paths:
            with self.subTest(path=path):
                missing = self.authorize(path, self.valid_identity())
                self.assertEqual(missing["status"], 403)
                self.assertEqual(missing["rate_limit_class"], "history")
                self.assertIn(MODULE.HISTORY_SCOPE, missing["required_scopes"])

                allowed = self.authorize(
                    path,
                    self.valid_identity([MODULE.GENERAL_SCOPE, MODULE.HISTORY_SCOPE]),
                )
                self.assertEqual(allowed["status"], 200)
                self.assertIs(allowed["allowed"], True)
                self.assertEqual(allowed["rate_limit_class"], "history")

    def test_rate_limit_contract_is_bounded(self) -> None:
        self.assertEqual(MODULE.rate_limit_contract(self.policy, "general"), {
            "requests": 120,
            "window_seconds": 60,
            "key": "session",
            "failure_status": 429,
        })
        self.assertEqual(MODULE.rate_limit_contract(self.policy, "history"), {
            "requests": 30,
            "window_seconds": 60,
            "key": "session",
            "failure_status": 429,
        })
        with self.assertRaises(KeyError):
            MODULE.rate_limit_contract(self.policy, "unbounded")

    def test_audit_event_uses_exact_redacted_fields(self) -> None:
        identity = self.valid_identity([MODULE.GENERAL_SCOPE, MODULE.HISTORY_SCOPE])
        decision = self.authorize("/edge1-ops/security/history/", identity)
        event = MODULE.build_audit_event(
            self.policy,
            decision,
            identity,
            "GET",
            "req-123",
            timestamp=dt.datetime(2026, 7, 30, 20, 45, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(tuple(event), MODULE.EXPECTED_AUDIT_FIELDS)
        self.assertEqual(event["actor_subject"], "operator-123")
        self.assertEqual(event["session_identifier_hash"], "a" * 64)
        self.assertEqual(event["authorization_decision"], "allowed")
        encoded = json.dumps(event, sort_keys=True)
        for forbidden in (
            "must-not-propagate",
            "operator@example.invalid",
            "token=",
            "/edge1-ops/security/history/",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_module_is_pure_and_has_no_session_or_listener_implementation(self) -> None:
        for token in (
            "http.server",
            "socket",
            "subprocess",
            "requests",
            "urllib.request",
            "ThreadingHTTPServer",
            "serve_forever",
            "Set-Cookie",
            "sqlite3",
            "systemctl",
            "apachectl",
        ):
            self.assertNotIn(token, self.source)
        self.assertIn("This module does not issue sessions", self.source)
        self.assertIn("validate_identity", self.source)
        self.assertIn("authorize_request", self.source)
        self.assertIn("build_audit_event", self.source)

    def test_apache_design_is_fail_closed_and_has_no_credentials(self) -> None:
        self.assertTrue(self.apache.startswith("# DESIGN ONLY"))
        self.assertEqual(APACHE_PATH.suffix, ".design")
        self.assertIn('Alias "/edge1-ops/" "/var/lib/wwcx-edge1-ops/current/"', self.apache)
        self.assertIn("Options -Indexes +FollowSymLinks", self.apache)
        self.assertIn("AllowOverride None", self.apache)
        self.assertIn("AuthType openid-connect", self.apache)
        self.assertIn("Require valid-user", self.apache)
        self.assertIn("Require method GET HEAD", self.apache)
        self.assertGreaterEqual(self.apache.count("Require all denied"), 4)
        self.assertIn('Header always set Cache-Control "no-store, max-age=0"', self.apache)
        self.assertIn('Header always set Referrer-Policy "no-referrer"', self.apache)
        self.assertIn('Header always set X-Content-Type-Options "nosniff"', self.apache)
        self.assertIn("Header always unset Access-Control-Allow-Origin", self.apache)
        for forbidden in (
            "OIDCProviderMetadataURL",
            "OIDCClientID",
            "OIDCClientSecret",
            "ProxyPass",
            "Require all granted",
        ):
            self.assertNotIn(forbidden, self.apache)
        self.assertFalse((ROOT / "deploy" / "install-edge1-authenticated-operations.sh").exists())


if __name__ == "__main__":
    unittest.main()
