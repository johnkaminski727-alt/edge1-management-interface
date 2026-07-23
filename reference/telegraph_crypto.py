#!/usr/bin/env python3
"""Cryptographic verification helpers for Telegraph reference documents."""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from reference.telegraph_federation_demo import canonical_json


def decode_base64url(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("base64url value must be a non-empty string")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def signing_key_from_identity(identity: dict[str, Any], key_id: str) -> Ed25519PublicKey:
    if identity.get("office_id") != key_id.split("#", 1)[0]:
        raise ValueError("signature key does not belong to identity office")
    for key in identity.get("keys", []):
        if (
            isinstance(key, dict)
            and key.get("key_id") == key_id
            and key.get("purpose") == "office_signing"
            and key.get("algorithm") == "Ed25519"
            and key.get("status") == "active"
        ):
            return Ed25519PublicKey.from_public_bytes(decode_base64url(key["public_key"]))
    raise ValueError("active signing key not found in identity")


def verify_document(document: dict[str, Any], identity: dict[str, Any]) -> bool:
    signature = document.get("signature")
    if not isinstance(signature, dict) or signature.get("algorithm") != "Ed25519":
        return False
    key_id = signature.get("key_id")
    value = signature.get("value")
    if not isinstance(key_id, str) or not isinstance(value, str):
        return False
    unsigned = {key: item for key, item in document.items() if key != "signature"}
    try:
        signing_key_from_identity(identity, key_id).verify(
            decode_base64url(value),
            canonical_json(unsigned),
        )
    except (InvalidSignature, ValueError, TypeError, KeyError):
        return False
    return True


def verify_identity(identity: dict[str, Any]) -> bool:
    office_id = identity.get("office_id")
    signature = identity.get("signature")
    if not isinstance(office_id, str) or not isinstance(signature, dict):
        return False
    key_id = signature.get("key_id")
    return isinstance(key_id, str) and key_id.startswith(office_id + "#") and verify_document(identity, identity)
