#!/usr/bin/env python3
from __future__ import annotations

import base64
import contextlib
import dataclasses
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from server.edge1_security_auth_gateway import (
    AuthenticationError,
    AuthorizationError,
    Edge1SecurityAuthGateway,
    GatewayConfig,
    SQLiteGatewayStore,
)

RSA_N = 27247446917748785485739314367877125842151069074351951386823105230878392233419365812545911863420296071102183419505529169437678414239132194821879904492556213161079722178625184552421628116693061037159858749972010659324417004504350072699193738628757161197621960829622031810701471573502506493795103075650214227249698605814195537168792365153518356202701392611990525299070458504153487162362742939035309468562723221537126462058414569374049075862737039386515961035973624298315976728512769686453337214691273368653531339323532679515926440966162559982717299873626944913002547525329171507027499111032609334195963213623824625513149
RSA_E = 65537
RSA_D = 5341226338592224958958954051667263312237587689369356538543363792988612616121253529972036097309314488387471968359667565493779919552773720293524133436316426911216430273414983077421314012163445918250647807511641072071360990842842751178212947802976078397025334250547846905901731927076105115061502498022160034445773158104888710474738035276164935874617272367144806263587871117363637704314499464372980437498657922453762251530221721040635044325503755358141638529845699931364114393045505868511824104237203459157479355716524458596589672435747761320710262280429686240301111517169985199073315511721376298183611187735032183325957
KID = "business159-test-2026"
DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def int_b64(value: int) -> str:
    return b64(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def sign_assertion(claims: dict, *, corrupt_signature: bool = False) -> str:
    header = {"alg": "RS256", "kid": KID, "typ": "JWT"}
    encoded_header = b64(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    encoded_claims = b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    message = f"{encoded_header}.{encoded_claims}".encode("ascii")
    size = (RSA_N.bit_length() + 7) // 8
    digest_info = DIGEST_INFO_PREFIX + hashlib.sha256(message).digest()
    encoded = b"\x00\x01" + (b"\xff" * (size - len(digest_info) - 3)) + b"\x00" + digest_info
    signature = pow(int.from_bytes(encoded, "big"), RSA_D, RSA_N).to_bytes(size, "big")
    if corrupt_signature:
        signature = bytes([signature[0] ^ 1]) + signature[1:]
    return f"{encoded_header}.{encoded_claims}.{b64(signature)}"


class Clock:
    def __init__(self, value: int = 1_800_000_000):
        self.value = value

    def __call__(self) -> float:
        return float(self.value)


class MemoryAudit:
    def __init__(self, fail: bool = False):
        self.events: list[dict] = []
        self.fail = fail

    def __call__(self, event: dict) -> str:
        if self.fail:
            raise OSError("audit unavailable")
        record = dict(event)
        event_id = f"edge1-auth-test-{len(self.events) + 1}"
        record["event_id"] = event_id
        self.events.append(record)
        return event_id


class GatewayTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.clock = Clock()
        self.jwks = self.root / "business159-jwks.json"
        self.jwks.write_text(
            json.dumps(
                {
                    "keys": [
                        {
                            "kty": "RSA",
                            "kid": KID,
                            "alg": "RS256",
                            "use": "sig",
                            "key_ops": ["verify"],
                            "n": int_b64(RSA_N),
                            "e": int_b64(RSA_E),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.audit = MemoryAudit()
        self.config = GatewayConfig(
            issuer="https://business159.ww.cx/wwcx-identity",
            audience="urn:wwcx:edge1:security-console",
            trusted_jwks_path=self.jwks,
            state_db_path=self.root / "state" / "security-auth.sqlite3",
            audit_path=self.root / "audit" / "security-auth.jsonl",
            assertion_max_lifetime_seconds=120,
            clock_skew_seconds=10,
            session_absolute_timeout_seconds=300,
            session_idle_timeout_seconds=180,
            session_token_bytes=32,
            enabled=True,
            deployment_authorized=True,
        )
        self.gateway = Edge1SecurityAuthGateway(self.config, audit=self.audit, now=self.clock)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def claims(self, **overrides) -> dict:
        value = {
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "sub": "wwcx-user-159-0001",
            "display_name": "Test Operator",
            "active": True,
            "role": "admin",
            "scope": ["edge1.security.read", "edge1.security.validate"],
            "iat": self.clock.value,
            "nbf": self.clock.value,
            "exp": self.clock.value + 60,
            "jti": "business159-assertion-00000001",
            "nonce": "business159-nonce-000000000001",
        }
        value.update(overrides)
        return value

    def exchange(self, **overrides):
        return self.gateway.exchange_assertion(sign_assertion(self.claims(**overrides)), "request-login-1")

    def test_valid_assertion_creates_hashed_edge1_session(self) -> None:
        token, context = self.exchange()
        self.assertGreaterEqual(len(token), 43)
        self.assertEqual(context.subject, "wwcx-user-159-0001")
        self.assertEqual(context.source_role, "admin")
        self.assertEqual(context.scopes, {"edge1.security.read", "edge1.security.validate"})
        self.assertEqual(context.authentication_event_id, "edge1-auth-test-1")
        with contextlib.closing(sqlite3.connect(self.config.state_db_path)) as connection:
            stored = connection.execute(
                "SELECT session_hash, scopes_json, authentication_event_id FROM sessions"
            ).fetchone()
        self.assertIsNotNone(stored)
        self.assertNotEqual(stored[0], token)
        self.assertEqual(stored[0], hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token, json.dumps(self.audit.events))
        self.gateway.authorize_action(token, "security.console.read", "request-read-1")
        self.gateway.authorize_action(token, "security.validate_config", "request-validate-1")

    def test_operations_event_id_is_correlated_without_tokens(self) -> None:
        token, context = self.exchange()
        correlation_event = self.gateway.correlate_operations_event(
            token,
            action_id="security.validate_config",
            operations_event_id="edge1-operations-event-abc123",
            request_id="request-operation-1",
        )
        self.assertEqual(correlation_event, "edge1-auth-test-3")
        record = self.audit.events[-1]
        self.assertEqual(record["operations_event_id"], "edge1-operations-event-abc123")
        self.assertEqual(record["authentication_event_id"], context.authentication_event_id)
        self.assertNotIn(token, json.dumps(record))

    def test_assertion_is_one_time(self) -> None:
        assertion = sign_assertion(self.claims())
        self.gateway.exchange_assertion(assertion, "request-login-1")
        with self.assertRaises(AuthenticationError):
            self.gateway.exchange_assertion(assertion, "request-login-2")
        self.assertEqual(self.audit.events[-1]["reason"], "assertion_replayed")

    def test_invalid_signature_wrong_audience_expiry_and_inactive_are_denied(self) -> None:
        cases = [
            sign_assertion(self.claims(), corrupt_signature=True),
            sign_assertion(self.claims(aud="urn:wrong:audience", jti="business159-assertion-00000002")),
            sign_assertion(
                self.claims(
                    iat=self.clock.value - 200,
                    nbf=self.clock.value - 200,
                    exp=self.clock.value - 100,
                    jti="business159-assertion-00000003",
                )
            ),
            sign_assertion(self.claims(active=False, jti="business159-assertion-00000004")),
        ]
        for index, assertion in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(AuthenticationError):
                self.gateway.exchange_assertion(assertion, f"request-denied-{index}")

    def test_unknown_and_mutation_scopes_deny_the_entire_assertion(self) -> None:
        for index, scopes in enumerate(
            [
                ["edge1.security.read", "edge1.security.unknown"],
                ["edge1.security.read", "edge1.security.rules.reload"],
            ]
        ):
            with self.subTest(scopes=scopes), self.assertRaises(AuthenticationError):
                self.gateway.exchange_assertion(
                    sign_assertion(
                        self.claims(scope=scopes, jti=f"business159-assertion-scope-{index:08d}")
                    ),
                    f"request-scope-{index}",
                )

    def test_exact_scope_and_action_allowlist_fail_closed(self) -> None:
        token, _ = self.exchange(scope=["edge1.security.read"])
        with self.assertRaises(AuthorizationError):
            self.gateway.authorize_action(token, "security.validate_config", "request-no-validate")
        with self.assertRaises(AuthorizationError):
            self.gateway.authorize_action(token, "security.rules.reload", "request-mutation")
        with self.assertRaises(AuthorizationError):
            self.gateway.authorize_action(token, "security.not_registered", "request-unknown")

    def test_idle_and_absolute_expiry_fail_closed(self) -> None:
        token, _ = self.exchange()
        self.clock.value += 180
        with self.assertRaises(AuthenticationError):
            self.gateway.authenticate_session(token, "request-idle-expired")
        token2, _ = self.gateway.exchange_assertion(
            sign_assertion(self.claims(jti="business159-assertion-00000009")), "request-login-2"
        )
        self.clock.value += 301
        with self.assertRaises(AuthenticationError):
            self.gateway.authenticate_session(token2, "request-absolute-expired")

    def test_logout_revokes_edge1_session_only(self) -> None:
        token, _ = self.exchange()
        self.gateway.logout(token, "request-logout-1")
        with self.assertRaises(AuthenticationError):
            self.gateway.authenticate_session(token, "request-after-logout")

    def test_disabled_gateway_denies_exchange_and_session_use(self) -> None:
        disabled = dataclasses.replace(
            self.config, enabled=False, deployment_authorized=False,
            state_db_path=self.root / "disabled" / "state.sqlite3",
        )
        gateway = Edge1SecurityAuthGateway(disabled, audit=self.audit, now=self.clock)
        with self.assertRaises(AuthenticationError):
            gateway.exchange_assertion(sign_assertion(self.claims()), "request-disabled")

    def test_audit_unavailable_prevents_session_creation(self) -> None:
        gateway = Edge1SecurityAuthGateway(
            self.config,
            store=SQLiteGatewayStore(self.config.state_db_path),
            audit=MemoryAudit(fail=True),
            now=self.clock,
        )
        with self.assertRaises(AuthenticationError):
            gateway.exchange_assertion(
                sign_assertion(self.claims(jti="business159-assertion-audit-0001")),
                "request-audit-failure",
            )
        with contextlib.closing(sqlite3.connect(self.config.state_db_path)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        self.assertEqual(count, 0)


class ConfigurationTestCase(unittest.TestCase):
    def test_repository_config_is_disabled_and_preserves_boundaries(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config_path = root / "config" / "security" / "edge1-security-auth-gateway.json"
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        config = GatewayConfig.from_mapping(raw)
        self.assertFalse(config.enabled)
        self.assertFalse(config.deployment_authorized)
        self.assertFalse(raw["boundaries"]["business159_database_access"])
        self.assertFalse(raw["boundaries"]["business159_cookie_acceptance"])
        self.assertFalse(raw["boundaries"]["password_material_acceptance"])
        self.assertFalse(raw["boundaries"]["mutations_enabled"])
        self.assertEqual(
            set(raw["permissions"]["initial"]),
            {"edge1.security.read", "edge1.security.validate"},
        )


if __name__ == "__main__":
    unittest.main()
