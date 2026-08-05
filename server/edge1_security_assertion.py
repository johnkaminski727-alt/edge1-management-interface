"""Strict RS256 validation for one-time Business159 identity assertions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .edge1_security_auth_core import (
    ALLOWED_SCOPES,
    MUTATION_SCOPES,
    AssertionIdentity,
    AuthenticationError,
    ConfigurationError,
    GatewayConfig,
    JTI_RE,
    SUBJECT_RE,
    nonempty_string,
    timestamp,
)

B64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SHA256_DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def validate_assertion(config: GatewayConfig, assertion: str, now: int) -> AssertionIdentity:
    if not isinstance(assertion, str) or len(assertion) > 16384:
        raise AuthenticationError("malformed_assertion")
    parts = assertion.split(".")
    if len(parts) != 3 or any(not part or not B64URL_RE.fullmatch(part) for part in parts):
        raise AuthenticationError("malformed_assertion")
    header = decode_json(parts[0], "header")
    claims = decode_json(parts[1], "claims")
    if set(header) - {"alg", "kid", "typ"}:
        raise AuthenticationError("unsupported_header")
    if header.get("alg") != "RS256" or header.get("typ", "JWT") != "JWT":
        raise AuthenticationError("unsupported_algorithm")
    try:
        kid = nonempty_string(header.get("kid"), "kid", 128)
    except ConfigurationError as exc:
        raise AuthenticationError("kid_invalid") from exc
    key = select_jwk(config.trusted_jwks_path, kid)
    signature = b64url_decode(parts[2])
    if not verify_rs256(f"{parts[0]}.{parts[1]}".encode("ascii"), signature, key):
        raise AuthenticationError("invalid_signature")

    required = {
        "iss", "aud", "sub", "display_name", "active", "role", "scope",
        "iat", "nbf", "exp", "jti", "nonce",
    }
    if set(claims) != required:
        raise AuthenticationError("claim_set_invalid")
    if claims.get("iss") != config.issuer or claims.get("aud") != config.audience:
        raise AuthenticationError("issuer_or_audience_invalid")
    if claims.get("active") is not True:
        raise AuthenticationError("identity_inactive")
    subject = claim_string(claims.get("sub"), "subject_invalid", 256)
    if not SUBJECT_RE.fullmatch(subject):
        raise AuthenticationError("subject_invalid")
    display_name = claim_string(claims.get("display_name"), "display_name_invalid", 256)
    source_role = claim_string(claims.get("role"), "role_invalid", 128)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", source_role):
        raise AuthenticationError("role_invalid")
    jti = claim_string(claims.get("jti"), "assertion_identifier_invalid", 256)
    nonce = claim_string(claims.get("nonce"), "assertion_identifier_invalid", 256)
    if not JTI_RE.fullmatch(jti) or not JTI_RE.fullmatch(nonce) or hmac.compare_digest(jti, nonce):
        raise AuthenticationError("assertion_identifier_invalid")

    iat = timestamp(claims.get("iat"), "iat")
    nbf = timestamp(claims.get("nbf"), "nbf")
    exp = timestamp(claims.get("exp"), "exp")
    skew = config.clock_skew_seconds
    if exp <= iat or exp - iat > config.assertion_max_lifetime_seconds:
        raise AuthenticationError("assertion_lifetime_invalid")
    if nbf < iat - skew or nbf > iat + skew:
        raise AuthenticationError("not_before_invalid")
    if iat > now + skew or nbf > now + skew or exp <= now - skew:
        raise AuthenticationError("assertion_time_invalid")
    if iat < now - config.assertion_max_lifetime_seconds - skew:
        raise AuthenticationError("assertion_too_old")

    scopes = parse_scopes(claims.get("scope"))
    if not scopes or not scopes.issubset(ALLOWED_SCOPES):
        raise AuthenticationError("scope_invalid")
    if scopes.intersection(MUTATION_SCOPES):
        raise AuthenticationError("mutation_scope_forbidden")
    return AssertionIdentity(
        subject=subject,
        display_name=display_name,
        source_role=source_role,
        scopes=frozenset(scopes),
        issued_at=iat,
        expires_at=exp,
        jti_hash=hashlib.sha256(
            f"{config.issuer}\x00{jti}\x00{nonce}".encode("utf-8")
        ).hexdigest(),
    )


def claim_string(value: Any, error: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or value != value.strip():
        raise AuthenticationError(error)
    return value


def parse_scopes(value: Any) -> set[str]:
    if isinstance(value, str):
        items = value.split()
    elif isinstance(value, list):
        items = value
    else:
        raise AuthenticationError("scope_invalid")
    if not items or any(not isinstance(item, str) or not item or len(item) > 128 for item in items):
        raise AuthenticationError("scope_invalid")
    if len(set(items)) != len(items):
        raise AuthenticationError("scope_invalid")
    return set(items)


def decode_json(segment: str, label: str) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(
            b64url_decode(segment).decode("utf-8"), object_pairs_hook=no_duplicates
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthenticationError(f"malformed_{label}") from exc
    if not isinstance(value, dict):
        raise AuthenticationError(f"malformed_{label}")
    return value


def b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value or not B64URL_RE.fullmatch(value):
        raise ValueError("invalid base64url")
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def select_jwk(path: Path, kid: str) -> Mapping[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthenticationError("trusted_keyset_unavailable") from exc
    if not isinstance(document, dict) or set(document) != {"keys"} or not isinstance(document["keys"], list):
        raise AuthenticationError("trusted_keyset_invalid")
    matches = [item for item in document["keys"] if isinstance(item, dict) and item.get("kid") == kid]
    if len(matches) != 1:
        raise AuthenticationError("trusted_key_not_found")
    key = matches[0]
    allowed = {"kty", "kid", "alg", "use", "key_ops", "n", "e"}
    if set(key) - allowed:
        raise AuthenticationError("trusted_key_invalid")
    if key.get("kty") != "RSA" or key.get("alg") != "RS256" or key.get("use", "sig") != "sig":
        raise AuthenticationError("trusted_key_invalid")
    if "key_ops" in key and key["key_ops"] != ["verify"]:
        raise AuthenticationError("trusted_key_invalid")
    return key


def verify_rs256(message: bytes, signature: bytes, key: Mapping[str, Any]) -> bool:
    try:
        n = int.from_bytes(b64url_decode(str(key["n"])), "big")
        e = int.from_bytes(b64url_decode(str(key["e"])), "big")
    except (KeyError, ValueError, TypeError):
        return False
    if n.bit_length() < 2048 or e < 3 or e % 2 == 0:
        return False
    size = (n.bit_length() + 7) // 8
    if len(signature) != size:
        return False
    value = int.from_bytes(signature, "big")
    if value <= 0 or value >= n:
        return False
    encoded = pow(value, e, n).to_bytes(size, "big")
    digest_info = SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(message).digest()
    padding_length = size - len(digest_info) - 3
    if padding_length < 8:
        return False
    expected = b"\x00\x01" + (b"\xff" * padding_length) + b"\x00" + digest_info
    return hmac.compare_digest(encoded, expected)
