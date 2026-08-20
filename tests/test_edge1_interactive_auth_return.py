from __future__ import annotations

import unittest
from urllib.parse import urlencode

from server.edge1_security_auth_core import AuthenticationError, SessionContext
from server.edge1_security_auth_http import (
    INTERACTIVE_LOGIN_URL,
    INTERACTIVE_RETURN_COOKIE_NAME,
    INTERACTIVE_RETURN_COOKIE_PATH,
    INTERACTIVE_RETURN_MAX_AGE,
    Edge1SecurityAuthHttpAdapter,
    HttpAdapterConfig,
    HttpRequest,
)


def config_mapping():
    return {
        "contract": "wwcx.edge1-security-auth-http.v1",
        "status": "staged_disabled",
        "enabled": True,
        "deployment_authorized": True,
        "live_route_authorized": True,
        "allowed_host": "edge1.ww.cx",
        "business159_origin": "https://ww.cx",
        "same_origin": "https://edge1.ww.cx",
        "routes": {
            "health": "/healthz",
            "console": "/edge1-ops/security/",
            "exchange": "/edge1-ops/session/exchange",
            "session": "/edge1-ops/session",
            "logout": "/edge1-ops/session/logout",
            "validate": "/edge1-ops/api/v1/security/validate",
            "redirect_after_exchange": "/edge1-ops/security/",
        },
        "cookies": {
            "session_name": "__Secure-wwcx_edge1_ops_session",
            "csrf_name": "__Secure-wwcx_edge1_ops_csrf",
            "path": "/edge1-ops/",
            "secure": True,
            "http_only_session": True,
            "same_site": "Strict",
            "persistent": False,
        },
        "request_limits": {
            "maximum_body_bytes": 20000,
            "exchange_requests": 10,
            "exchange_window_seconds": 600,
            "session_requests": 120,
            "session_window_seconds": 60,
            "action_requests": 6,
            "action_window_seconds": 60,
            "logout_requests": 20,
            "logout_window_seconds": 600,
            "action_inflight_timeout_seconds": 60,
            "action_cooldown_seconds": 3,
        },
        "operations_api": {
            "origin": "http://127.0.0.1:8097",
            "secret_path": "/etc/edge1-operations-api.secret",
            "timeout_seconds": 15,
            "allowed_action": "security.validate_config",
        },
        "boundaries": {
            "loopback_only": True,
            "trusted_proxy_required": True,
            "csrf_required_for_authenticated_post": True,
            "raw_assertion_storage": False,
            "raw_session_storage": False,
            "raw_operations_output_to_browser": False,
            "mutation_actions_enabled": False,
        },
    }


class FakeStore:
    def __init__(self):
        self.csrf = None

    def allow_rate(self, *args, **kwargs):
        return True

    def set_csrf(self, session_hash, csrf_hash, expires_at):
        self.csrf = (session_hash, csrf_hash, expires_at)


class FakeGateway:
    def __init__(self):
        self.store = FakeStore()

    def exchange_assertion(self, assertion, request_id):
        if assertion != "valid-assertion":
            raise AuthenticationError("denied")
        return "s" * 43, SessionContext(
            "wwcx-user-42",
            "Test Administrator",
            "admin",
            frozenset({"edge1.security.read", "edge1.security.validate"}),
            1800000000,
            1800000300,
            1800000000,
            "edge1-auth-login",
            "a" * 64,
        )

    def authenticate_session(self, token, request_id):
        raise AuthenticationError("session_missing")


class FakeOperations:
    pass


class InteractiveAuthReturnTests(unittest.TestCase):
    def setUp(self):
        self.adapter = Edge1SecurityAuthHttpAdapter(
            HttpAdapterConfig.from_mapping(config_mapping()),
            FakeGateway(),
            FakeOperations(),
            now=lambda: 1800000000,
        )

    def request(self, method, path, *, headers=None, body=b""):
        return self.adapter.handle(
            HttpRequest(method, path, headers or {}, body, "127.0.0.1", "https", "edge1.ww.cx")
        )

    @staticmethod
    def values(response, name):
        return [value for key, value in response.headers if key.lower() == name.lower()]

    @staticmethod
    def exchange_body():
        return urlencode({
            "assertion": "valid-assertion",
            "request_id": "b159-0123456789abcdef0123456789abcdef",
        }).encode()

    def exchange(self, *, origin="https://ww.cx", cookie=None, extra_headers=None):
        headers = {
            "Origin": origin,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if cookie:
            headers["Cookie"] = cookie
        if extra_headers:
            headers.update(extra_headers)
        return self.request(
            "POST",
            "/edge1-ops/session/exchange",
            headers=headers,
            body=self.exchange_body(),
        )

    def test_human_consoles_redirect_but_api_and_session_stay_401(self):
        for path, token in (
            ("/edge1-ops/security/", "security"),
            ("/edge1-ops/snmp/", "snmp"),
        ):
            response = self.request("GET", path)
            self.assertEqual(response.status, 302)
            self.assertEqual(self.values(response, "Location"), [INTERACTIVE_LOGIN_URL])
            cookie = self.values(response, "Set-Cookie")[0]
            self.assertIn(f"{INTERACTIVE_RETURN_COOKIE_NAME}={token};", cookie)
            self.assertIn(f"Path={INTERACTIVE_RETURN_COOKIE_PATH}", cookie)
            self.assertIn("Max-Age=900", cookie)
            self.assertIn("Secure; HttpOnly; SameSite=Strict", cookie)
            self.assertNotIn("Domain=", cookie)
        self.assertEqual(self.request("GET", "/edge1-ops/session").status, 401)
        self.assertEqual(self.request("GET", "/edge1-ops/api/v1/snmp/health").status, 401)

    def test_return_cookie_lifetime_is_bounded(self):
        self.assertEqual(INTERACTIVE_RETURN_MAX_AGE, 900)

    def test_snmp_return_token_redirects_to_snmp_and_is_cleared(self):
        response = self.exchange(cookie=f"{INTERACTIVE_RETURN_COOKIE_NAME}=snmp")
        self.assertEqual(response.status, 303)
        self.assertEqual(self.values(response, "Location"), ["/edge1-ops/snmp/"])
        cookies = self.values(response, "Set-Cookie")
        self.assertEqual(len(cookies), 3)
        self.assertTrue(any(f"{INTERACTIVE_RETURN_COOKIE_NAME}=;" in value and "Max-Age=0" in value for value in cookies))

    def test_security_return_token_redirects_to_security(self):
        response = self.exchange(cookie=f"{INTERACTIVE_RETURN_COOKIE_NAME}=security")
        self.assertEqual(response.status, 303)
        self.assertEqual(self.values(response, "Location"), ["/edge1-ops/security/"])

    def test_missing_or_tampered_return_token_uses_fixed_fallback(self):
        missing = self.exchange()
        self.assertEqual(self.values(missing, "Location"), ["/edge1-ops/security/"])
        tampered = self.exchange(cookie=f"{INTERACTIVE_RETURN_COOKIE_NAME}=https://evil.example/")
        self.assertEqual(self.values(tampered, "Location"), ["/edge1-ops/security/"])
        self.assertNotIn("evil.example", self.values(tampered, "Location")[0])

    def test_session_and_csrf_cookie_security_attributes_are_preserved(self):
        response = self.exchange(cookie=f"{INTERACTIVE_RETURN_COOKIE_NAME}=snmp")
        cookies = self.values(response, "Set-Cookie")
        session = next(value for value in cookies if value.startswith("__Secure-wwcx_edge1_ops_session="))
        csrf = next(value for value in cookies if value.startswith("__Secure-wwcx_edge1_ops_csrf="))
        self.assertIn("Path=/edge1-ops/; Secure; HttpOnly; SameSite=Strict", session)
        self.assertIn("Path=/edge1-ops/; Secure; SameSite=Strict", csrf)
        self.assertNotIn("HttpOnly", csrf)

    def test_null_origin_is_allowed_only_for_same_site_top_level_navigation(self):
        accepted = self.exchange(
            origin="null",
            extra_headers={
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
            },
        )
        self.assertEqual(accepted.status, 303)
        rejected = self.exchange(
            origin="null",
            extra_headers={
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
            },
        )
        self.assertEqual(rejected.status, 403)
        self.assertEqual(self.exchange(origin="https://evil.example").status, 403)


if __name__ == "__main__":
    unittest.main()
