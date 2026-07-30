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
EXPECTED_STATUSES = {
    "unknown_route_status": 404,
    "unauthenticated_api_status": 401,
    "authenticated_forbidden_status": 403,
    "method_not_allowed_status": 405,
}
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
    "login_started",
    "login_succeeded",
    "login_failed",
    "logout",
    "session_expired",
    "authorization_denied",
    "rate_limited",
    "restricted_read",
)
EXPECTED_AUDIT_FIELDS = (
    "schema_version",
    "timestamp",
    "request_id",
    "actor_subject",
    "session_identifier_hash",
    "method",
    "path_classification",
    "required_scopes",
    "authorization_decision",
    "status",
    "reason",
)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def load_policy(path: Path = DEFAULT_POLICY) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("authenticated operations policy must be an object")
    return value


def _require_exact_keys(value: Any, expected: Iterable[str], label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if set(value) != set(expected):
        raise ValueError(f"{label} fields do not match the contract")
    return value


def _validate_provider(provider: Any) -> Dict[str, Any]:
    keys = (
        "protocol", "flow", "pkce_method", "discovery_required", "state_required",
        "nonce_required", "mfa_required", "subject_claim",
        "audience_validation_required", "issuer_allowlist_required",
        "configuration_external", "configuration_path", "client_secret_path",
        "refresh_tokens_allowed", "raw_token_storage_allowed",
        "preferred_apache_adapter", "adapter_inventory_verified",
        "identity_provider_selected",
    )
    value = _require_exact_keys(provider, keys, "provider")
    expected = {
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
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise ValueError(f"provider.{key} does not match the contract")
    for key in ("adapter_inventory_verified", "identity_provider_selected"):
        if not isinstance(value.get(key), bool):
            raise ValueError(f"provider.{key} must be boolean")
    return value


def _validate_session(session: Any) -> Dict[str, Any]:
    keys = (
        "server_side_required", "opaque_identifier_bytes", "identifier_storage",
        "idle_timeout_seconds", "absolute_timeout_seconds", "clock_skew_seconds",
        "rotate_on_authentication", "rotate_on_scope_change", "invalidate_on_logout",
        "persistent_session", "cookie",
    )
    value = _require_exact_keys(session, keys, "session")
    exact = {
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
    for key, expected in exact.items():
        if value.get(key) != expected:
            raise ValueError(f"session.{key} does not match the contract")
    cookie = _require_exact_keys(value.get("cookie"), EXPECTED_COOKIE, "session.cookie")
    if cookie != EXPECTED_COOKIE:
        raise ValueError("session.cookie does not match the contract")
    return value


def _validate_request_boundary(boundary: Any) -> Dict[str, Any]:
    keys = (
        "allowed_methods", "maximum_path_bytes", "query_credentials_forbidden",
        "cross_origin_requests_allowed", "unknown_route_status",
        "unauthenticated_api_status", "authenticated_forbidden_status",
        "method_not_allowed_status", "browser_navigation_challenge",
        "api_redirect_on_auth_failure",
    )
    value = _require_exact_keys(boundary, keys, "request_boundary")
    if tuple(value.get("allowed_methods") or ()) != ALLOWED_METHODS:
        raise ValueError("request_boundary.allowed_methods must be GET and HEAD")
    if value.get("maximum_path_bytes") != 2048:
        raise ValueError("request_boundary.maximum_path_bytes must be 2048")
    if value.get("query_credentials_forbidden") is not True:
        raise ValueError("query credentials must be forbidden")
    if value.get("cross_origin_requests_allowed") is not False:
        raise ValueError("cross-origin requests must be forbidden")
    for key, expected in EXPECTED_STATUSES.items():
        if value.get(key) != expected:
            raise ValueError(f"request_boundary.{key} does not match the contract")
    if value.get("browser_navigation_challenge") != "oidc_redirect":
        raise ValueError("browser navigation challenge must use OIDC redirect")
    if value.get("api_redirect_on_auth_failure") is not False:
        raise ValueError("API authentication failures must not redirect")
    return value


def _validate_authentication_routes(routes: Any) -> Dict[str, Any]:
    expected = {
        "redirect_uri": "https://edge1.ww.cx/edge1-ops/oidc/callback",
        "post_logout_uri": "https://edge1.ww.cx/edge1-status/",
        "local_logout_path": "/edge1-ops/session/logout",
        "local_logout_method": "POST",
        "local_logout_csrf_required": True,
    }
    value = _require_exact_keys(routes, expected, "authentication_routes")
    if value != expected:
        raise ValueError("authentication routes do not match the contract")
    return value


def _validate_route_rules(rules: Any) -> List[Dict[str, Any]]:
    if not isinstance(rules, list) or len(rules) != 9:
        raise ValueError("route_rules must contain exactly nine entries")
    seen: set[Tuple[str, str]] = set()
    validated: List[Dict[str, Any]] = []
    allowed_scopes = {GENERAL_SCOPE, HISTORY_SCOPE}
    for index, rule in enumerate(rules):
        value = _require_exact_keys(
            rule,
            ("path", "match", "classification", "required_scopes", "rate_limit_class"),
            f"route_rules[{index}]",
        )
        path = value.get("path")
        match = value.get("match")
        classification = value.get("classification")
        scopes = value.get("required_scopes")
        rate_class = value.get("rate_limit_class")
        if not isinstance(path, str) or not path.startswith(RESTRICTED_ROOT):
            raise ValueError("restricted route escapes /edge1-ops/")
        if "?" in path or "#" in path or "%" in path or "\\" in path or "//" in path[1:]:
            raise ValueError("restricted route path is ambiguous")
        if match not in {"exact", "prefix"}:
            raise ValueError("unsupported route match type")
        if (path, match) in seen:
            raise ValueError("duplicate restricted route rule")
        seen.add((path, match))
        if not isinstance(classification, str) or not classification or len(classification) > 128:
            raise ValueError("invalid route classification")
        if not isinstance(scopes, list) or not scopes or len(scopes) > 2:
            raise ValueError("invalid required scope list")
        if len(set(scopes)) != len(scopes) or any(scope not in allowed_scopes for scope in scopes):
            raise ValueError("route requires an unsupported or duplicate scope")
        if GENERAL_SCOPE not in scopes:
            raise ValueError("all restricted routes require general detail scope")
        if "history" in classification and HISTORY_SCOPE not in scopes:
            raise ValueError("history routes require the history scope")
        if rate_class not in {"general", "history"}:
            raise ValueError("invalid rate limit class")
        if "history" in classification and rate_class != "history":
            raise ValueError("history route must use history rate limit")
        validated.append(value)
    if not any(rule["path"] == RESTRICTED_ROOT and rule["match"] == "exact" for rule in validated):
        raise ValueError("restricted landing route is missing")
    return validated


def _validate_rate_limits(rate_limits: Any) -> Dict[str, Any]:
    value = _require_exact_keys(
        rate_limits,
        ("general", "history", "authentication_failures", "failure_status"),
        "rate_limits",
    )
    expected = {
        "general": {"requests": 120, "window_seconds": 60, "key": "session"},
        "history": {"requests": 30, "window_seconds": 60, "key": "session"},
        "authentication_failures": {
            "requests": 10,
            "window_seconds": 600,
            "key": "source_and_subject",
        },
        "failure_status": 429,
    }
    if value != expected:
        raise ValueError("rate limit contract does not match the accepted design")
    return value


def _validate_audit(audit: Any) -> Dict[str, Any]:
    keys = (
        "required", "append_only", "storage_root", "file_mode", "directory_mode",
        "events", "fields", "cookies_recorded", "tokens_recorded",
        "query_strings_recorded", "response_bodies_recorded",
    )
    value = _require_exact_keys(audit, keys, "audit")
    exact = {
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
    for key, expected in exact.items():
        if value.get(key) != expected:
            raise ValueError(f"audit.{key} does not match the contract")
    if tuple(value.get("events") or ()) != EXPECTED_AUDIT_EVENTS:
        raise ValueError("audit event allowlist does not match the contract")
    if tuple(value.get("fields") or ()) != EXPECTED_AUDIT_FIELDS:
        raise ValueError("audit field allowlist does not match the contract")
    return value


def _validate_response_headers(headers: Any) -> Dict[str, Any]:
    value = _require_exact_keys(headers, EXPECTED_HEADERS, "response_headers")
    if value != EXPECTED_HEADERS:
        raise ValueError("restricted response headers do not match the contract")
    return value


def _validate_failure_behavior(behavior: Any) -> Dict[str, Any]:
    expected = {
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
    value = _require_exact_keys(behavior, expected, "failure_behavior")
    if value != expected:
        raise ValueError("failure behavior does not match the contract")
    return value


def _validate_acceptance(acceptance: Any) -> Dict[str, Any]:
    keys = (
        "fresh_live_inventory_required", "provider_selected_and_verified",
        "apache_adapter_verified", "session_store_verified",
        "authorized_route_matrix_verified", "unauthorized_route_matrix_verified",
        "audit_verified", "rate_limit_verified", "no_anonymous_fallback",
        "no_new_tcp_listener", "tls_identity_unchanged",
        "traffic_controls_changed", "live_change_authorized",
    )
    value = _require_exact_keys(acceptance, keys, "acceptance")
    for key in (
        "fresh_live_inventory_required", "no_anonymous_fallback",
        "no_new_tcp_listener", "tls_identity_unchanged",
    ):
        if value.get(key) is not True:
            raise ValueError(f"acceptance.{key} must be true")
    if value.get("traffic_controls_changed") is not False:
        raise ValueError("traffic controls must remain unchanged")
    for key in (
        "provider_selected_and_verified", "apache_adapter_verified",
        "session_store_verified", "authorized_route_matrix_verified",
        "unauthorized_route_matrix_verified", "audit_verified",
        "rate_limit_verified", "live_change_authorized",
    ):
        if not isinstance(value.get(key), bool):
            raise ValueError(f"acceptance.{key} must be boolean")
    return value


def validate_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    if policy.get("contract") != CONTRACT:
        raise ValueError("unsupported authenticated operations policy contract")
    if policy.get("status") != "design_only":
        raise ValueError("policy status must remain design_only")
    if policy.get("domain") != "edge1.ww.cx":
        raise ValueError("policy domain is not approved")
    if policy.get("restricted_root") != RESTRICTED_ROOT or policy.get("public_root") != PUBLIC_ROOT:
        raise ValueError("route roots do not match the accepted boundary")
    if policy.get("anonymous_fallback") is not False:
        raise ValueError("anonymous fallback must remain disabled")
    for key in (
        "enabled", "deployment_authorized", "authentication_change_authorized",
        "live_route_authorized",
    ):
        if not isinstance(policy.get(key), bool):
            raise ValueError(f"{key} must be boolean")

    provider = _validate_provider(policy.get("provider"))
    _validate_session(policy.get("session"))
    _validate_request_boundary(policy.get("request_boundary"))
    _validate_authentication_routes(policy.get("authentication_routes"))
    scopes = _require_exact_keys(policy.get("scopes"), ("general_detail", "suricata_history"), "scopes")
    if scopes != {"general_detail": GENERAL_SCOPE, "suricata_history": HISTORY_SCOPE}:
        raise ValueError("scope contract does not match the accepted design")
    _validate_route_rules(policy.get("route_rules"))
    _validate_rate_limits(policy.get("rate_limits"))
    _validate_audit(policy.get("audit"))
    _validate_response_headers(policy.get("response_headers"))
    _validate_failure_behavior(policy.get("failure_behavior"))
    acceptance = _validate_acceptance(policy.get("acceptance"))

    activation_flags = (
        policy["enabled"],
        policy["deployment_authorized"],
        policy["authentication_change_authorized"],
        policy["live_route_authorized"],
    )
    if any(activation_flags):
        if not all(activation_flags):
            raise ValueError("partial authenticated-boundary activation is forbidden")
        if not provider["adapter_inventory_verified"] or not provider["identity_provider_selected"]:
            raise ValueError("provider and Apache adapter must be verified before activation")
        required_acceptance = (
            "provider_selected_and_verified", "apache_adapter_verified",
            "session_store_verified", "authorized_route_matrix_verified",
            "unauthorized_route_matrix_verified", "audit_verified",
            "rate_limit_verified", "live_change_authorized",
        )
        if any(acceptance.get(key) is not True for key in required_acceptance):
            raise ValueError("all live acceptance gates are required before activation")
    return policy


def normalize_path(path: Any, maximum_bytes: int = 2048) -> Optional[str]:
    if not isinstance(path, str) or not path:
        return None
    try:
        encoded = path.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if len(encoded) > maximum_bytes or "\x00" in path:
        return None
    if not path.startswith(RESTRICTED_ROOT):
        return None
    if any(token in path for token in ("?", "#", "%", "\\")):
        return None
    if "//" in path[1:]:
        return None
    segments = path.split("/")
    if any(segment in {".", ".."} for segment in segments):
        return None
    return path


def match_route(policy: Dict[str, Any], path: str) -> Optional[Dict[str, Any]]:
    rules = sorted(policy["route_rules"], key=lambda item: len(item["path"]), reverse=True)
    for rule in rules:
        if rule["match"] == "exact" and path == rule["path"]:
            return rule
        if rule["match"] == "prefix" and path.startswith(rule["path"]):
            return rule
    return None


def _coerce_epoch(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_identity(
    identity: Any,
    policy: Dict[str, Any],
    *,
    now_epoch: Optional[int] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
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

    issued_at = _coerce_epoch(identity.get("issued_at"))
    last_seen_at = _coerce_epoch(identity.get("last_seen_at"))
    expires_at = _coerce_epoch(identity.get("expires_at"))
    if issued_at is None or last_seen_at is None or expires_at is None:
        return False, "session_invalid", None
    current = int(utc_now().timestamp()) if now_epoch is None else int(now_epoch)
    session = policy["session"]
    skew = int(session["clock_skew_seconds"])
    if issued_at > current + skew or last_seen_at > current + skew:
        return False, "session_invalid", None
    if expires_at <= current:
        return False, "session_expired", None
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
    safe_identity = {
        "subject": subject.strip(),
        "session_identifier_hash": session_hash,
        "scopes": tuple(scopes),
    }
    return True, "authenticated", safe_identity


def _decision(
    *,
    allowed: bool,
    status: int,
    reason: str,
    classification: str,
    required_scopes: Sequence[str] = (),
    rate_limit_class: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "allowed": bool(allowed),
        "status": int(status),
        "reason": reason,
        "classification": classification,
        "required_scopes": list(required_scopes),
        "rate_limit_class": rate_limit_class,
    }


def authorize_request(
    policy: Dict[str, Any],
    method: Any,
    path: Any,
    identity: Any,
    *,
    now_epoch: Optional[int] = None,
) -> Dict[str, Any]:
    validate_policy(policy)
    boundary = policy["request_boundary"]
    normalized = normalize_path(path, int(boundary["maximum_path_bytes"]))
    if normalized is None:
        return _decision(
            allowed=False,
            status=int(boundary["unknown_route_status"]),
            reason="not_found",
            classification="unknown",
        )
    route = match_route(policy, normalized)
    if route is None:
        return _decision(
            allowed=False,
            status=int(boundary["unknown_route_status"]),
            reason="not_found",
            classification="unknown",
        )

    valid, auth_reason, safe_identity = validate_identity(identity, policy, now_epoch=now_epoch)
    if not valid:
        return _decision(
            allowed=False,
            status=int(boundary["unauthenticated_api_status"]),
            reason=auth_reason,
            classification=route["classification"],
            required_scopes=route["required_scopes"],
            rate_limit_class=route["rate_limit_class"],
        )

    normalized_method = method.upper() if isinstance(method, str) else ""
    if normalized_method not in tuple(boundary["allowed_methods"]):
        return _decision(
            allowed=False,
            status=int(boundary["method_not_allowed_status"]),
            reason="method_not_allowed",
            classification=route["classification"],
            required_scopes=route["required_scopes"],
            rate_limit_class=route["rate_limit_class"],
        )

    granted = set(safe_identity["scopes"] if safe_identity else ())
    required = tuple(route["required_scopes"])
    if any(scope not in granted for scope in required):
        return _decision(
            allowed=False,
            status=int(boundary["authenticated_forbidden_status"]),
            reason="scope_missing",
            classification=route["classification"],
            required_scopes=required,
            rate_limit_class=route["rate_limit_class"],
        )
    return _decision(
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


def build_audit_event(
    policy: Dict[str, Any],
    decision: Dict[str, Any],
    identity: Any,
    method: Any,
    request_id: Any,
    *,
    timestamp: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    validate_policy(policy)
    safe_request_id = request_id if isinstance(request_id, str) and REQUEST_ID_RE.fullmatch(request_id) else "invalid"
    subject = "anonymous"
    session_hash = ""
    if isinstance(identity, dict):
        candidate_subject = identity.get("subject")
        if isinstance(candidate_subject, str) and candidate_subject.strip() and len(candidate_subject) <= 256:
            subject = candidate_subject.strip()
        candidate_hash = identity.get("session_identifier_hash")
        if isinstance(candidate_hash, str) and SESSION_HASH_RE.fullmatch(candidate_hash):
            session_hash = candidate_hash
    status = int(decision.get("status", 500))
    event = {
        "schema_version": "wwcx.edge1-ops-audit-event.v1",
        "timestamp": iso(timestamp or utc_now()),
        "request_id": safe_request_id,
        "actor_subject": subject,
        "session_identifier_hash": session_hash,
        "method": method.upper() if isinstance(method, str) else "UNKNOWN",
        "path_classification": str(decision.get("classification") or "unknown"),
        "required_scopes": list(decision.get("required_scopes") or ()),
        "authorization_decision": "allowed" if decision.get("allowed") is True else "denied",
        "status": status,
        "reason": str(decision.get("reason") or "unknown"),
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
