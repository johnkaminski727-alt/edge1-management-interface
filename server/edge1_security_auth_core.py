"""Shared contracts for the Business159 to Edge1 security identity bridge."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "wwcx.edge1-security-auth-gateway.v1"
ALLOWED_SCOPES = frozenset({
    "edge1.security.read", "edge1.security.validate",
    "edge1.vpn.self.read", "edge1.vpn.self.enroll", "edge1.vpn.self.rename",
    "edge1.vpn.self.revoke", "edge1.vpn.self.policy.accept",
})
MUTATION_SCOPES = frozenset(
    {
        "edge1.security.rules.reload",
        "edge1.security.logs.rotate",
        "edge1.security.restart",
    }
)
ACTION_SCOPES = {
    "security.console.read": "edge1.security.read",
    "security.validate_config": "edge1.security.validate",
}
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SUBJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
JTI_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~-]{15,255}$")


class GatewayError(Exception):
    """Base error for denied gateway operations."""


class ConfigurationError(GatewayError):
    """Raised when gateway configuration cannot be trusted."""


class AuthenticationError(GatewayError):
    """Raised when an assertion or session cannot be authenticated."""


class AuthorizationError(GatewayError):
    """Raised when an authenticated session lacks an exact permission."""


class AuditUnavailableError(GatewayError):
    """Raised when required audit evidence cannot be written."""


@dataclasses.dataclass(frozen=True)
class GatewayConfig:
    issuer: str
    audience: str
    trusted_jwks_path: Path
    state_db_path: Path
    audit_path: Path
    assertion_max_lifetime_seconds: int = 120
    clock_skew_seconds: int = 10
    session_absolute_timeout_seconds: int = 900
    session_idle_timeout_seconds: int = 600
    session_token_bytes: int = 32
    enabled: bool = False
    deployment_authorized: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GatewayConfig":
        expected = {
            "contract", "status", "enabled", "deployment_authorized",
            "live_route_authorized", "issuer", "audience", "trusted_jwks_path",
            "state_db_path", "audit_path", "assertion", "session",
            "permissions", "boundaries",
        }
        if set(value) != expected:
            raise ConfigurationError("gateway configuration fields do not match the contract")
        if value.get("contract") != CONTRACT:
            raise ConfigurationError("gateway configuration contract is invalid")
        if value.get("status") != "staged_disabled":
            raise ConfigurationError("gateway status must remain staged_disabled in repository defaults")
        if not isinstance(value.get("enabled"), bool) or not isinstance(
            value.get("deployment_authorized"), bool
        ):
            raise ConfigurationError("gateway activation flags must be boolean")
        if value.get("live_route_authorized") is not False:
            raise ConfigurationError("repository configuration cannot authorize a live route")
        if value.get("enabled") and not value.get("deployment_authorized"):
            raise ConfigurationError("gateway cannot be enabled without deployment authorization")

        issuer = nonempty_string(value.get("issuer"), "issuer", 512)
        audience = nonempty_string(value.get("audience"), "audience", 512)
        if issuer == audience:
            raise ConfigurationError("issuer and audience must be distinct")

        assertion = exact_object(
            value.get("assertion"),
            {
                "algorithm", "required_claims", "scope_claim",
                "maximum_lifetime_seconds", "clock_skew_seconds",
                "one_time_required",
            },
            "assertion",
        )
        if assertion["algorithm"] != "RS256":
            raise ConfigurationError("only RS256 assertions are accepted")
        if assertion["required_claims"] != [
            "iss", "aud", "sub", "display_name", "active", "role", "scope",
            "iat", "nbf", "exp", "jti", "nonce",
        ]:
            raise ConfigurationError("required assertion claims do not match the contract")
        if assertion["scope_claim"] != "scope" or assertion["one_time_required"] is not True:
            raise ConfigurationError("assertion scope and replay contract is invalid")
        max_lifetime = bounded_int(
            assertion["maximum_lifetime_seconds"], 15, 300,
            "assertion.maximum_lifetime_seconds",
        )
        clock_skew = bounded_int(
            assertion["clock_skew_seconds"], 0, 60,
            "assertion.clock_skew_seconds",
        )

        session = exact_object(
            value.get("session"),
            {
                "opaque_identifier_bytes", "identifier_storage",
                "absolute_timeout_seconds", "idle_timeout_seconds", "persistent",
            },
            "session",
        )
        token_bytes = bounded_int(
            session["opaque_identifier_bytes"], 32, 64,
            "session.opaque_identifier_bytes",
        )
        absolute_timeout = bounded_int(
            session["absolute_timeout_seconds"], 60, 28800,
            "session.absolute_timeout_seconds",
        )
        idle_timeout = bounded_int(
            session["idle_timeout_seconds"], 60, absolute_timeout,
            "session.idle_timeout_seconds",
        )
        if session["identifier_storage"] != "sha256_only" or session["persistent"] is not False:
            raise ConfigurationError("session storage contract is invalid")

        permissions = exact_object(
            value.get("permissions"),
            {"initial", "mutations", "unknown_scope_behavior"},
            "permissions",
        )
        if set(permissions["initial"]) != ALLOWED_SCOPES:
            raise ConfigurationError("initial permissions do not match the approved boundary")
        if set(permissions["mutations"]) != MUTATION_SCOPES:
            raise ConfigurationError("mutation permission registry does not match the boundary")
        if permissions["unknown_scope_behavior"] != "deny_assertion":
            raise ConfigurationError("unknown scopes must deny the assertion")

        boundaries = exact_object(
            value.get("boundaries"),
            {
                "business159_database_access", "business159_cookie_acceptance",
                "password_material_acceptance", "raw_assertion_storage",
                "raw_session_storage", "browser_operations_api_access",
                "mutations_enabled",
            },
            "boundaries",
        )
        if any(boundaries[key] is not False for key in boundaries):
            raise ConfigurationError("a prohibited trust-boundary capability is enabled")

        return cls(
            issuer=issuer,
            audience=audience,
            trusted_jwks_path=Path(nonempty_string(
                value.get("trusted_jwks_path"), "trusted_jwks_path", 4096
            )),
            state_db_path=Path(nonempty_string(
                value.get("state_db_path"), "state_db_path", 4096
            )),
            audit_path=Path(nonempty_string(
                value.get("audit_path"), "audit_path", 4096
            )),
            assertion_max_lifetime_seconds=max_lifetime,
            clock_skew_seconds=clock_skew,
            session_absolute_timeout_seconds=absolute_timeout,
            session_idle_timeout_seconds=idle_timeout,
            session_token_bytes=token_bytes,
            enabled=bool(value["enabled"]),
            deployment_authorized=bool(value["deployment_authorized"]),
        )

    @classmethod
    def from_path(cls, path: Path) -> "GatewayConfig":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError("gateway configuration is unavailable") from exc
        if not isinstance(value, dict):
            raise ConfigurationError("gateway configuration must be a JSON object")
        return cls.from_mapping(value)


@dataclasses.dataclass(frozen=True)
class AssertionIdentity:
    subject: str
    display_name: str
    source_role: str
    scopes: frozenset[str]
    issued_at: int
    expires_at: int
    jti_hash: str


@dataclasses.dataclass(frozen=True)
class SessionContext:
    subject: str
    display_name: str
    source_role: str
    scopes: frozenset[str]
    issued_at: int
    expires_at: int
    last_seen_at: int
    authentication_event_id: str
    session_identifier_hash: str


def exact_object(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ConfigurationError(f"{label} fields do not match the contract")
    return value


def nonempty_string(value: Any, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or value != value.strip():
        raise ConfigurationError(f"{label} must be a bounded non-empty string")
    return value


def bounded_int(value: Any, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ConfigurationError(f"{label} is outside the accepted range")
    return value


def timestamp(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AuthenticationError(f"{label}_invalid")
    return value


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_event_id(value: Any) -> bool:
    return isinstance(value, str) and bool(EVENT_ID_RE.fullmatch(value))


def require_event_id(value: Any, label: str) -> str:
    if not valid_event_id(value):
        raise AuthenticationError(f"{label}_invalid")
    return str(value)


def safe_reason(exc: GatewayError) -> str:
    reason = str(exc)
    if not re.fullmatch(r"[a-z0-9_]{1,64}", reason):
        return "authentication_denied"
    return reason
