#!/usr/bin/env python3
"""Pure fail-closed policy evaluator for the future authenticated Edge1 surface.

This module does not issue sessions, read credentials or tokens, open a listener,
write audit records, or alter Apache. It validates the committed design policy
and evaluates already-authenticated server-side session claims.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "security" / "edge1-authenticated-operations-policy.json"
CONTRACT = "wwcx.edge1-authenticated-operations-policy.v1"
RESTRICTED_ROOT = "/edge1-ops/"
PUBLIC_ROOT = "/edge1-status/"
GENERAL_SCOPE = "edge1.status.detail.read"
HISTORY_SCOPE = "security.suricata.history.read"
SESSION_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ALLOWED_METHODS = ("GET", "HEAD")

EXPECTED_COOKIE = {
    "name": "__Secure-wwcx_edge1_ops_session",
    "path": RESTRICTED_ROOT,
    "domain": None,
    "secure": True,
    "http_only": True,
    "same_site": "Strict",
}
EXPECTED_HEADERS = {
    "cache_control": "no-store, max-age=0",
    "content_security_policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "referrer_policy": "no-referrer",
    "x_content_type_options": "nosniff",
    "permissions_policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "cross_origin_opener_policy": "same-origin",
    "cross_origin_resource_policy": "same-origin",
    "cors_allow_origin": None,
    "directory_listing": False,
}
EXPECTED_AUDIT_EVENTS = (
    "login_started", "login_succeeded", "login_failed", "logout",
    "session_expired", "authorization_denied", "rate_limited", "restricted_read",
)
EXPECTED_AUDIT_FIELDS = (
    "schema_version", "timestamp", "request_id", "actor_subject",
    "session_identifier_hash", "method", "path_classification",
    "required_scopes", "authorization_decision", "status", "reason",
)
EXPECTED_ROUTE_RULES = (
    {
        "path": "/edge1-ops/security/history/",
        "match": "prefix",
        "classification": "restricted_security_history",
        "required_scopes": [GENERAL_SCOPE, HISTORY_SCOPE],
        "rate_limit_class": "history",
    },
    {
        "path": "/edge1-ops/api/v1/security/suricata/history",
        "match": "prefix",
        "classification": "restricted_security_history_api",
        "required_scopes": [GENERAL_SCOPE, HISTORY_SCOPE],
        "rate_limit_class": "history",
    },
    {
        "path": "/edge1-ops/security/",
        "match": "prefix",
        "classification": "restricted_security_operations",
        "required_scopes": [GENERAL_SCOPE],
        "rate_limit_class": "general",
    },
    {
        "path": "/edge1-ops/network-defense/",
        "match": "prefix",
        "classification": "restricted_network_operations",
        "required_scopes": [GENERAL_SCOPE],
        "rate_limit_class": "general",
    },
    {
        "path": "/edge1-ops/bitcoin/",
        "match": "prefix",
        "classification": "restricted_financial_operations",
        "required_scopes": [GENERAL_SCOPE],
        "rate_limit_class": "general",
    },
    {
        "path": "/edge1-ops/mining/",
        "match": "prefix",
        "classification": "restricted_financial_operations",
        "required_scopes": [GENERAL_SCOPE],
        "rate_limit_class": "general",
    },
    {
        "path": "/edge1-ops/reports/",
        "match": "prefix",
        "classification": "restricted_evidence_and_reports",
        "required_scopes": [GENERAL_SCOPE],
        "rate_limit_class": "general",
    },
    {
        "path": "/edge1-ops/data/",
        "match": "prefix",
        "classification": "restricted_operations_data",
        "required_scopes": [GENERAL_SCOPE],
        "rate_limit_class": "general",
    },
    {
        "path": RESTRICTED_ROOT,
        "match": "exact",
        "classification": "restricted_operations_landing",
        "required_scopes": [GENERAL_SCOPE],
        "rate_limit_class": "general",
    },
)
EXPECTED_RATE_LIMITS = {
    "general": {"requests": 120, "window_seconds": 60, "key": "session"},
    "history": {"requests": 30, "window_seconds": 60, "key": "session"},
    "authentication_failures": {
        "requests": 10,
        "window_seconds": 600,
        "key": "source_and_subject",
    },
    "failure_status": 429,
}
TOP_LEVEL_FIELDS = {
    "contract", "status", "enabled", "deployment_authorized",
    "authentication_change_authorized", "live_route_authorized", "domain",
    "restricted_root", "public_root", "anonymous_fallback", "provider",
    "session", "request_boundary", "authentication_routes", "scopes",
    "route_rules", "rate_limits", "audit", "response_headers",
    "failure_behavior", "acceptance",
}


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def load_policy(path: Path = DEFAULT_POLICY) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("authenticated operations policy must be an object")
    return value


def require_fields(value: Any, fields: Iterable[str], label: str) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label} fields do not match the contract")
    return value


def validate_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(policy, dict) or set(policy) != TOP_LEVEL_FIELDS:
        raise ValueError("policy fields do not match the contract")
    fixed_top = {
        "contract": CONTRACT,
        "status": "design_only",
        "domain": "edge1.ww.cx",
        "restricted_root": RESTRICTED_ROOT,
        "public_root": PUBLIC_ROOT,
        "anonymous_fallback": False,
    }
    for key, expected in fixed_top.items():
        if policy.get(key) != expected:
            raise ValueError(f"{key} does not match the accepted boundary")
    activation_keys = (
        "enabled", "deployment_authorized", "authentication_change_authorized",
        "live_route_authorized",
    )
    if any(not isinstance(policy.get(key), bool) for key in activation_keys):
        raise ValueError("activation flags must be boolean")

    provider_fields = (
        "protocol", "flow", "pkce_method", "discovery_required", "state_required",
        "nonce_required", "mfa_required", "subject_claim",
        "audience_validation_required", "issuer_allowlist_required",
        "configuration_external", "configuration_path", "client_secret_path",
        "refresh_tokens_allowed", "raw_token_storage_allowed",
        "preferred_apache_adapter", "adapter_inventory_verified",
        "identity_provider_selected",
    )
    provider = require_fields(policy["provider"], provider_fields, "provider")
    provider_fixed = {
        "protocol": "openid_connect",
        "flow": "authorization_code",
        "pkce_method": "S256",
        "discovery_required": True,
        "state_required": True,
        "nonce_required": True,
        "mfa_required": True,
        "subject_claim": "sub",
        "audience_validation_required": True,
        "issuer_allowlist_required": True,
        "configuration_external": True,
        "configuration_path": "/etc/wwcx-edge1-ops/oidc.json",
        "client_secret_path": "/etc/wwcx-edge1-ops/client-secret",
        "refresh_tokens_allowed": False,
        "raw_token_storage_allowed": False,
        "preferred_apache_adapter": "mod_auth_openidc",
    }
    for key, expected in provider_fixed.items():
        if provider.get(key) != expected:
            raise ValueError(f"provider.{key} does not match the contract")
    if any(not isinstance(provider.get(key), bool) for key in (
        "adapter_inventory_verified", "identity_provider_selected"
    )):
        raise ValueError("provider verification fields must be boolean")

    session_fields = (
        "server_side_required", "opaque_identifier_bytes", "identifier_storage",
        "idle_timeout_seconds", "absolute_timeout_seconds", "clock_skew_seconds",
        "rotate_on_authentication", "rotate_on_scope_change", "invalidate_on_logout",
        "persistent_session", "cookie",
    )
    session = require_fields(policy["session"], session_fields, "session")
    session_fixed = {
        "server_side_required": True,
        "opaque_identifier_bytes": 32,
        "identifier_storage": "sha256_only",
        "idle_timeout_seconds": 900,
        "absolute_timeout_seconds": 28800,
        "clock_skew_seconds": 60,
        "rotate_on_authentication": True,
        "rotate_on_scope_change": True,
        "invalidate_on_logout": True,
        "persistent_session": False,
    }
    for key, expected in session_fixed.items():
        if session.get(key) != expected:
            raise ValueError(f"session.{key} does not match the contract")
    cookie = require_fields(session["cookie"], EXPECTED_COOKIE, "session.cookie")
    if cookie != EXPECTED_COOKIE:
        raise ValueError("session.cookie does not match the contract")

    boundary_expected = {
        "allowed_methods": ["GET", "HEAD"],
        "maximum_path_bytes": 2048,
        "query_credentials_forbidden": True,
        "cross_origin_requests_allowed": False,
        "unknown_route_status": 404,
        "unauthenticated_api_status": 401,
        "authenticated_forbidden_status": 403,
        "method_not_allowed_status": 405,
        "browser_navigation_challenge": "oidc_redirect",
        "api_redirect_on_auth_failure": False,
    }
    boundary = require_fields(policy["request_boundary"], boundary_expected, "request_boundary")
    if boundary != boundary_expected:
        raise ValueError("request boundary does not match the contract")

    auth_routes_expected = {
        "redirect_uri": "https://edge1.ww.cx/edge1-ops/oidc/callback",
        "post_logout_uri": "https://edge1.ww.cx/edge1-status/",
        "local_logout_path": "/edge1-ops/session/logout",
        "local_logout_method": "POST",
        "local_logout_csrf_required": True,
    }
    auth_routes = require_fields(policy["authentication_routes"], auth_routes_expected, "authentication_routes")
    if auth_routes != auth_routes_expected:
        raise ValueError("authentication routes do not match the contract")

    scopes_expected = {"general_detail": GENERAL_SCOPE, "suricata_history": HISTORY_SCOPE}
    scopes = require_fields(policy["scopes"], scopes_expected, "scopes")
    if scopes != scopes_expected:
        raise ValueError("scope contract does not match the accepted design")
    if tuple(policy["route_rules"]) != EXPECTED_ROUTE_RULES:
        raise ValueError("route rule allowlist does not match the accepted design")
    if policy["rate_limits"] != EXPECTED_RATE_LIMITS:
        raise ValueError("rate limit contract does not match the accepted design")

    audit_fields = (
        "required", "append_only", "storage_root", "file_mode", "directory_mode",
        "events", "fields", "cookies_recorded", "tokens_recorded",
        "query_strings_recorded", "response_bodies_recorded",
    )
    audit = require_fields(policy["audit"], audit_fields, "audit")
    audit_fixed = {
        "required": True,
        "append_only": True,
        "storage_root": "/var/lib/wwcx-edge1-ops/audit",
        "file_mode": "0600",
        "directory_mode": "0700",
        "cookies_recorded": False,
        "tokens_recorded": False,
        "query_strings_recorded": False,
        "response_bodies_recorded": False,
    }
    for key, expected in audit_fixed.items():
        if audit.get(key) != expected:
            raise ValueError(f"audit.{key} does not match the contract")
    if tuple(audit["events"]) != EXPECTED_AUDIT_EVENTS:
        raise ValueError("audit event allowlist does not match the contract")
    if tuple(audit["fields"]) != EXPECTED_AUDIT_FIELDS:
        raise ValueError("audit field allowlist does not match the contract")

    headers = require_fields(policy["response_headers"], EXPECTED_HEADERS, "response_headers")
    if headers != EXPECTED_HEADERS:
        raise ValueError("response headers do not match the contract")
    failure_expected = {
        "identity_unresolved": "deny",
        "policy_unavailable": "deny",
        "session_store_unavailable": "deny",
        "issuer_untrusted": "deny",
        "audience_invalid": "deny",
        "mfa_missing": "deny",
        "scope_missing": "deny",
        "unknown_route": "not_found",
        "error_details_public": False,
        "audit_rejection_required": True,
    }
    failure = require_fields(policy["failure_behavior"], failure_expected, "failure_behavior")
    if failure != failure_expected:
        raise ValueError("failure behavior does not match the contract")

    acceptance_fields = (
        "fresh_live_inventory_required", "provider_selected_and_verified",
        "apache_adapter_verified", "session_store_verified",
        "authorized_route_matrix_verified", "unauthorized_route_matrix_verified",
        "audit_verified", "rate_limit_verified", "no_anonymous_fallback",
        "no_new_tcp_listener", "tls_identity_unchanged", "traffic_controls_changed",
        "live_change_authorized",
    )
    acceptance = require_fields(policy["acceptance"], acceptance_fields, "acceptance")
    for key in ("fresh_live_inventory_required", "no_anonymous_fallback", "no_new_tcp_listener", "tls_identity_unchanged"):
        if acceptance.get(key) is not True:
            raise ValueError(f"acceptance.{key} must be true")
    if acceptance.get("traffic_controls_changed") is not False:
        raise ValueError("traffic controls must remain unchanged")
    verification_keys = (
        "provider_selected_and_verified", "apache_adapter_verified",
        "session_store_verified", "authorized_route_matrix_verified",
        "unauthorized_route_matrix_verified", "audit_verified", "rate_limit_verified",
        "live_change_authorized",
    )
    if any(not isinstance(acceptance.get(key), bool) for key in verification_keys):
        raise ValueError("acceptance verification fields must be boolean")

    activation = tuple(policy[key] for key in activation_keys)
    if any(activation):
        if not all(activation):
            raise ValueError("partial authenticated-boundary activation is forbidden")
        if not provider["adapter_inventory_verified"] or not provider["identity_provider_selected"]:
            raise ValueError("provider and Apache adapter must be verified before activation")
        if any(acceptance[key] is not True for key in verification_keys):
            raise ValueError("all live acceptance gates are required before activation")
    return policy


def normalize_path(path: Any, maximum_bytes: int = 2048) -> Optional[str]:
    if not isinstance(path, str) or not path:
        return None
    try:
        encoded = path.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if len(encoded) > maximum_bytes or any(ord(char) < 32 or ord(char) == 127 for char in path):
        return None
    if not path.startswith(RESTRICTED_ROOT):
        return None
    if any(token in path for token in ("?", "#", "%", "\\")) or "//" in path[1:]:
        return None
    if any(segment in {".", ".."} for segment in path.split("/")):
        return None
    return path


def match_route(policy: Dict[str, Any], path: str) -> Optional[Dict[str, Any]]:
    for rule in sorted(policy["route_rules"], key=lambda item: len(item["path"]), reverse=True):
        base = rule["path"]
        if rule["match"] == "exact" and path == base:
            return rule
        if rule["match"] == "prefix":
            if base.endswith("/") and path.startswith(base):
                return rule
            if not base.endswith("/") and (path == base or path.startswith(base + "/")):
                return rule
    return None


def coerce_epoch(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_identity(identity: Any, policy: Dict[str, Any], *, now_epoch: Optional[int] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    if not isinstance(identity, dict) or identity.get("authenticated") is not True:
        return False, "identity_unresolved", None
    subject = identity.get("subject")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 256:
        return False, "identity_unresolved", None
    if identity.get("issuer_trusted") is not True:
        return False, "issuer_untrusted", None
    if identity.get("audience_valid") is not True:
        return False, "audience_invalid", None
    if identity.get("mfa") is not True:
        return False, "mfa_missing", None
    session_hash = identity.get("session_identifier_hash")
    if not isinstance(session_hash, str) or SESSION_HASH_RE.fullmatch(session_hash) is None:
        return False, "session_invalid", None

    issued_at = coerce_epoch(identity.get("issued_at"))
    last_seen_at = coerce_epoch(identity.get("last_seen_at"))
    expires_at = coerce_epoch(identity.get("expires_at"))
    if issued_at is None or last_seen_at is None or expires_at is None:
        return False, "session_invalid", None
    current = int(utc_now().timestamp()) if now_epoch is None else int(now_epoch)
    session = policy["session"]
    skew = int(session["clock_skew_seconds"])
    if issued_at > last_seen_at or issued_at > current + skew or last_seen_at > current + skew:
        return False, "session_invalid", None
    if expires_at <= current:
        return False, "session_expired", None
    if expires_at <= issued_at:
        return False, "session_invalid", None
    if current - last_seen_at > int(session["idle_timeout_seconds"]):
        return False, "session_idle_timeout", None
    if current - issued_at > int(session["absolute_timeout_seconds"]):
        return False, "session_absolute_timeout", None
    if expires_at - issued_at > int(session["absolute_timeout_seconds"]) + skew:
        return False, "session_invalid", None

    scopes = identity.get("scopes")
    if not isinstance(scopes, list) or len(scopes) > 64:
        return False, "session_invalid", None
    if any(not isinstance(scope, str) or not scope or len(scope) > 128 for scope in scopes):
        return False, "session_invalid", None
    if len(scopes) != len(set(scopes)):
        return False, "session_invalid", None
    return True, "authenticated", {
        "subject": subject.strip(),
        "session_identifier_hash": session_hash,
        "scopes": tuple(scopes),
    }


def decision(*, allowed: bool, status: int, reason: str, classification: str, required_scopes: Sequence[str] = (), rate_limit_class: Optional[str] = None) -> Dict[str, Any]:
    return {
        "allowed": bool(allowed),
        "status": int(status),
        "reason": reason,
        "classification": classification,
        "required_scopes": list(required_scopes),
        "rate_limit_class": rate_limit_class,
    }


def authorize_request(policy: Dict[str, Any], method: Any, path: Any, identity: Any, *, now_epoch: Optional[int] = None) -> Dict[str, Any]:
    validate_policy(policy)
    boundary = policy["request_boundary"]
    normalized = normalize_path(path, int(boundary["maximum_path_bytes"]))
    route = match_route(policy, normalized) if normalized is not None else None
    if route is None:
        return decision(allowed=False, status=404, reason="not_found", classification="unknown")

    valid, auth_reason, safe_identity = validate_identity(identity, policy, now_epoch=now_epoch)
    if not valid:
        return decision(
            allowed=False,
            status=401,
            reason=auth_reason,
            classification=route["classification"],
            required_scopes=route["required_scopes"],
            rate_limit_class=route["rate_limit_class"],
        )
    normalized_method = method.upper() if isinstance(method, str) else ""
    if normalized_method not in ALLOWED_METHODS:
        return decision(
            allowed=False,
            status=405,
            reason="method_not_allowed",
            classification=route["classification"],
            required_scopes=route["required_scopes"],
            rate_limit_class=route["rate_limit_class"],
        )
    granted = set(safe_identity["scopes"] if safe_identity else ())
    required = tuple(route["required_scopes"])
    if any(scope not in granted for scope in required):
        return decision(
            allowed=False,
            status=403,
            reason="scope_missing",
            classification=route["classification"],
            required_scopes=required,
            rate_limit_class=route["rate_limit_class"],
        )
    return decision(
        allowed=True,
        status=200,
        reason="authorized",
        classification=route["classification"],
        required_scopes=required,
        rate_limit_class=route["rate_limit_class"],
    )


def rate_limit_contract(policy: Dict[str, Any], rate_limit_class: str) -> Dict[str, Any]:
    validate_policy(policy)
    if rate_limit_class not in {"general", "history", "authentication_failures"}:
        raise KeyError("unknown rate limit class")
    value = policy["rate_limits"][rate_limit_class]
    return {
        "requests": int(value["requests"]),
        "window_seconds": int(value["window_seconds"]),
        "key": str(value["key"]),
        "failure_status": int(policy["rate_limits"]["failure_status"]),
    }


def build_audit_event(policy: Dict[str, Any], request_decision: Dict[str, Any], identity: Any, method: Any, request_id: Any, *, timestamp: Optional[dt.datetime] = None) -> Dict[str, Any]:
    validate_policy(policy)
    safe_request_id = request_id if isinstance(request_id, str) and REQUEST_ID_RE.fullmatch(request_id) else "invalid"
    subject = "anonymous"
    session_hash = ""
    if isinstance(identity, dict) and identity.get("authenticated") is True:
        candidate_subject = identity.get("subject")
        if isinstance(candidate_subject, str) and candidate_subject.strip() and len(candidate_subject) <= 256:
            subject = candidate_subject.strip()
        candidate_hash = identity.get("session_identifier_hash")
        if isinstance(candidate_hash, str) and SESSION_HASH_RE.fullmatch(candidate_hash):
            session_hash = candidate_hash
    event = {
        "schema_version": "wwcx.edge1-ops-audit-event.v1",
        "timestamp": iso(timestamp or utc_now()),
        "request_id": safe_request_id,
        "actor_subject": subject,
        "session_identifier_hash": session_hash,
        "method": method.upper() if isinstance(method, str) else "UNKNOWN",
        "path_classification": str(request_decision.get("classification") or "unknown"),
        "required_scopes": list(request_decision.get("required_scopes") or ()),
        "authorization_decision": "allowed" if request_decision.get("allowed") is True else "denied",
        "status": int(request_decision.get("status", 500)),
        "reason": str(request_decision.get("reason") or "unknown"),
    }
    if tuple(event) != EXPECTED_AUDIT_FIELDS:
        raise ValueError("audit event fields do not match the allowlist")
    return event


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args()
    policy = validate_policy(load_policy(args.policy))
    print(json.dumps({
        "ok": True,
        "state": policy["status"],
        "enabled": policy["enabled"],
        "deployment_authorized": policy["deployment_authorized"],
        "live_route_authorized": policy["live_route_authorized"],
        "anonymous_fallback": policy["anonymous_fallback"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
