#!/usr/bin/env python3
"""Signing-key rotation and revocation for Telegraph federation identities.

This reference keyring preserves historical public keys, requires every normal
rotation to be authorized by the currently active key, and supports explicit
emergency revocation records. Private key material remains local and is never
serialized into identity or lifecycle documents.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from reference.telegraph_crypto import decode_base64url
from reference.telegraph_federation_demo import b64, canonical_json


def _public_text(key: Ed25519PublicKey) -> str:
    return b64(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def _unsigned(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "signature"}


@dataclass
class ManagedSigningKey:
    key_id: str
    public_key: str
    not_before: int
    not_after: int | None = None
    status: str = "active"
    revoked_at: int | None = None
    revocation_reason: str | None = None

    def document(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "key_id": self.key_id,
            "purpose": "office_signing",
            "algorithm": "Ed25519",
            "public_key": self.public_key,
            "not_before": self.not_before,
            "status": self.status,
        }
        if self.not_after is not None:
            result["not_after"] = self.not_after
        if self.revoked_at is not None:
            result["revoked_at"] = self.revoked_at
        if self.revocation_reason is not None:
            result["revocation_reason"] = self.revocation_reason
        return result


@dataclass
class TelegraphKeyring:
    office_id: str
    overlap_seconds: int = 86400
    sequence: int = 1
    active_key_id: str = field(init=False)
    private_keys: dict[str, Ed25519PrivateKey] = field(default_factory=dict)
    keys: dict[str, ManagedSigningKey] = field(default_factory=dict)
    lifecycle: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.office_id or "#" in self.office_id:
            raise ValueError("invalid office_id")
        if self.overlap_seconds < 0:
            raise ValueError("overlap_seconds cannot be negative")
        now = int(time.time())
        private = Ed25519PrivateKey.generate()
        key_id = f"{self.office_id}#signing-1"
        self.private_keys[key_id] = private
        self.keys[key_id] = ManagedSigningKey(key_id, _public_text(private.public_key()), now)
        self.active_key_id = key_id

    def sign(self, document: dict[str, Any], key_id: str | None = None) -> dict[str, str]:
        selected = key_id or self.active_key_id
        managed = self.keys.get(selected)
        private = self.private_keys.get(selected)
        if managed is None or private is None or managed.status not in {"active", "retiring"}:
            raise ValueError("signing key is unavailable")
        return {
            "algorithm": "Ed25519",
            "key_id": selected,
            "value": b64(private.sign(canonical_json(_unsigned(document)))),
        }

    def identity_keys(self) -> list[dict[str, Any]]:
        return [self.keys[key_id].document() for key_id in sorted(self.keys)]

    def rotate(self, now: int | None = None) -> dict[str, Any]:
        effective = int(time.time()) if now is None else int(now)
        old_key_id = self.active_key_id
        old = self.keys[old_key_id]
        generation = max(int(key_id.rsplit("-", 1)[-1]) for key_id in self.keys) + 1
        new_key_id = f"{self.office_id}#signing-{generation}"
        private = Ed25519PrivateKey.generate()
        new = ManagedSigningKey(new_key_id, _public_text(private.public_key()), effective)
        manifest: dict[str, Any] = {
            "version": "1.0",
            "kind": "signing_key_rotation",
            "office_id": self.office_id,
            "sequence": self.sequence,
            "issued_at": effective,
            "previous_key_id": old_key_id,
            "new_key": new.document(),
            "overlap_until": effective + self.overlap_seconds,
        }
        manifest["signature"] = self.sign(manifest, old_key_id)
        old.status = "retiring"
        old.not_after = effective + self.overlap_seconds
        self.private_keys[new_key_id] = private
        self.keys[new_key_id] = new
        self.active_key_id = new_key_id
        self.sequence += 1
        self.lifecycle.append(manifest)
        return manifest

    def retire_expired(self, now: int | None = None) -> list[str]:
        effective = int(time.time()) if now is None else int(now)
        retired: list[str] = []
        for managed in self.keys.values():
            if managed.status == "retiring" and managed.not_after is not None and effective >= managed.not_after:
                managed.status = "retired"
                retired.append(managed.key_id)
        return retired

    def revoke(self, key_id: str, reason: str, now: int | None = None) -> dict[str, Any]:
        if not reason:
            raise ValueError("revocation reason is required")
        target = self.keys.get(key_id)
        if target is None:
            raise KeyError(key_id)
        effective = int(time.time()) if now is None else int(now)
        authorizer = self.active_key_id
        if key_id == authorizer:
            raise ValueError("rotate before revoking the active key")
        record: dict[str, Any] = {
            "version": "1.0",
            "kind": "signing_key_revocation",
            "office_id": self.office_id,
            "sequence": self.sequence,
            "issued_at": effective,
            "revoked_key_id": key_id,
            "reason": reason,
            "authorized_by": authorizer,
        }
        record["signature"] = self.sign(record, authorizer)
        target.status = "revoked"
        target.revoked_at = effective
        target.revocation_reason = reason
        self.sequence += 1
        self.lifecycle.append(record)
        return record

    def verify(self, document: dict[str, Any], signed_at: int | None = None) -> bool:
        signature = document.get("signature")
        if not isinstance(signature, dict) or signature.get("algorithm") != "Ed25519":
            return False
        key_id = signature.get("key_id")
        value = signature.get("value")
        managed = self.keys.get(key_id) if isinstance(key_id, str) else None
        if managed is None or not isinstance(value, str):
            return False
        moment = int(time.time()) if signed_at is None else int(signed_at)
        if moment < managed.not_before:
            return False
        if managed.status == "revoked" and managed.revoked_at is not None and moment >= managed.revoked_at:
            return False
        if managed.not_after is not None and moment > managed.not_after:
            return False
        try:
            Ed25519PublicKey.from_public_bytes(decode_base64url(managed.public_key)).verify(
                decode_base64url(value), canonical_json(_unsigned(document))
            )
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True


def apply_rotation_manifest(
    known_keys: dict[str, ManagedSigningKey],
    manifest: dict[str, Any],
    expected_office_id: str,
) -> ManagedSigningKey:
    if manifest.get("kind") != "signing_key_rotation" or manifest.get("office_id") != expected_office_id:
        raise ValueError("invalid rotation manifest")
    previous_key_id = manifest.get("previous_key_id")
    new_document = manifest.get("new_key")
    previous = known_keys.get(previous_key_id)
    if previous is None or not isinstance(new_document, dict):
        raise ValueError("rotation trust anchor is unavailable")
    signature = manifest.get("signature")
    if not isinstance(signature, dict) or signature.get("key_id") != previous_key_id:
        raise ValueError("rotation is not authorized by previous key")
    try:
        Ed25519PublicKey.from_public_bytes(decode_base64url(previous.public_key)).verify(
            decode_base64url(signature["value"]), canonical_json(_unsigned(manifest))
        )
    except (InvalidSignature, ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid rotation signature") from exc
    key_id = new_document.get("key_id")
    if not isinstance(key_id, str) or not key_id.startswith(expected_office_id + "#"):
        raise ValueError("new key does not belong to office")
    new = ManagedSigningKey(
        key_id=key_id,
        public_key=str(new_document["public_key"]),
        not_before=int(new_document["not_before"]),
        not_after=new_document.get("not_after"),
        status=str(new_document.get("status", "active")),
    )
    overlap_until = int(manifest["overlap_until"])
    previous.status = "retiring"
    previous.not_after = overlap_until
    known_keys[new.key_id] = new
    return new
