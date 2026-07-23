#!/usr/bin/env python3
"""Executable two-office Telegraph Federation reference demonstration.

This is a non-production interoperability fixture. It intentionally keeps
networking in-process while exercising the protocol's trust, routing, replay,
code-word commitment, encrypted-envelope, and signed-receipt concepts.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install the 'cryptography' package to run this demo") from exc


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


@dataclass
class ReplayCache:
    seen: dict[str, float] = field(default_factory=dict)

    def accept(self, nonce: str, now: float, window_seconds: int) -> bool:
        self.seen = {key: ts for key, ts in self.seen.items() if now - ts <= window_seconds}
        if nonce in self.seen:
            return False
        self.seen[nonce] = now
        return True


@dataclass
class Office:
    office_id: str
    media: set[str]
    security: set[str]
    trust: dict[str, str]
    signing_key: Ed25519PrivateKey = field(default_factory=Ed25519PrivateKey.generate)
    replay_cache: ReplayCache = field(default_factory=ReplayCache)
    receipt_sequence: int = 0
    last_receipt_digest: str | None = None

    def public_key(self) -> str:
        from cryptography.hazmat.primitives import serialization

        raw = self.signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return b64(raw)

    def sign(self, document: dict[str, Any]) -> dict[str, str]:
        unsigned = {key: value for key, value in document.items() if key != "signature"}
        return {
            "algorithm": "Ed25519",
            "key_id": f"{self.office_id}#signing-1",
            "value": b64(self.signing_key.sign(canonical_json(unsigned))),
        }

    def identity_document(self) -> dict[str, Any]:
        document = {
            "version": "1.0",
            "office_id": self.office_id,
            "issued_at": "2026-07-22T00:00:00Z",
            "sequence": 1,
            "keys": [{
                "key_id": f"{self.office_id}#signing-1",
                "purpose": "office_signing",
                "algorithm": "Ed25519",
                "public_key": self.public_key(),
                "not_before": "2026-07-22T00:00:00Z",
                "status": "active",
            }],
            "services": [{"type": "federation_https", "uri": f"https://{self.office_id}/telegraph"}],
            "policy": {
                "accepted_envelope_versions": ["1.0"],
                "max_clock_skew_seconds": 300,
                "replay_window_seconds": 3600,
                "requires_mutual_tls": True,
                "allows_store_and_forward": True,
                "allows_gateway_decryption": False,
                "requires_code_word_hashing_in_metadata": True,
            },
        }
        document["signature"] = self.sign(document)
        return document

    def route(self, peer: "Office", requirements: dict[str, Any]) -> dict[str, Any]:
        reasons: list[str] = []
        if self.trust.get(peer.office_id) not in {"trusted", "observed"}:
            reasons.append("insufficient_trust")
        missing_security = set(requirements["security"]) - peer.security
        missing_media = set(requirements["media"]) - peer.media
        if missing_security:
            reasons.append("security_mismatch")
        if missing_media:
            reasons.append("media_mismatch")

        eligible = not reasons
        decision = {
            "version": "1.0",
            "decision_id": secrets.token_hex(16),
            "message_id": requirements["message_id"],
            "evaluated_at": "2026-07-22T00:00:01Z",
            "origin_office": self.office_id,
            "destination_office": peer.office_id,
            "requirements": {
                "minimum_trust": "observed",
                "security": sorted(requirements["security"]),
                "media": sorted(requirements["media"]),
                "store_and_forward": "allowed",
                "downgrade_policy": "forbid",
                "required_code_word_purposes": ["message_verification"],
            },
            "selected_path": {
                "path_id": f"direct:{self.office_id}:{peer.office_id}",
                "offices": [peer.office_id],
                "eligible": eligible,
                "score": 1000 if eligible else 0,
                "estimated_latency_ms": 1,
                "security_state": "end_to_end_encrypted" if eligible else "transport_encrypted_only",
                "media": sorted(self.media & peer.media),
                "downgrades": [],
                "rejection_reasons": reasons,
            },
            "result": "selected" if eligible else "rejected",
            "reason_codes": reasons,
            "disclosures": [],
        }
        decision["signature"] = self.sign(decision)
        return decision

    def receipt(self, envelope: dict[str, Any], event: str, duplicate: bool = False) -> dict[str, Any]:
        self.receipt_sequence += 1
        receipt = {
            "version": "1.0",
            "receipt_id": secrets.token_hex(16),
            "message_id": envelope["message_id"],
            "office_id": self.office_id,
            "event": event,
            "recorded_at": "2026-07-22T00:00:02Z",
            "sequence": self.receipt_sequence,
            "message_digest": sha256(canonical_json(envelope)),
            "security_state": envelope["security_state"],
            "code_word_evidence": [{
                "purpose": "message_verification",
                "evidence_type": "verified_match",
                "evidence": envelope["code_word_commitment"],
            }],
            "replay": {
                "nonce": envelope["nonce"],
                "first_seen_at": "2026-07-22T00:00:02Z",
                "duplicate_count": 1 if duplicate else 0,
            },
        }
        if self.last_receipt_digest:
            receipt["previous_receipt_digest"] = self.last_receipt_digest
        receipt["signature"] = self.sign(receipt)
        self.last_receipt_digest = sha256(canonical_json(receipt))
        return receipt


def encrypt_envelope(sender: Office, recipient: Office, message: str, code_word: str) -> tuple[dict[str, Any], bytes]:
    key = ChaCha20Poly1305.generate_key()
    nonce = secrets.token_bytes(12)
    message_id = secrets.token_hex(16)
    metadata = {
        "message_id": message_id,
        "origin": sender.office_id,
        "destination": recipient.office_id,
        "security_state": "end_to_end_encrypted",
        "code_word_commitment": sha256(code_word.encode("utf-8")),
    }
    ciphertext = ChaCha20Poly1305(key).encrypt(nonce, message.encode("utf-8"), canonical_json(metadata))
    envelope = {
        **metadata,
        "version": "1.0",
        "nonce": b64(nonce),
        "payload": {"encoding": "base64url", "ciphertext": b64(ciphertext)},
    }
    envelope["signature"] = sender.sign(envelope)
    return envelope, key


def decrypt_envelope(envelope: dict[str, Any], key: bytes) -> str:
    padding = "=" * (-len(envelope["nonce"]) % 4)
    nonce = base64.urlsafe_b64decode(envelope["nonce"] + padding)
    ciphertext_text = envelope["payload"]["ciphertext"]
    ciphertext = base64.urlsafe_b64decode(ciphertext_text + "=" * (-len(ciphertext_text) % 4))
    metadata = {key: envelope[key] for key in ("message_id", "origin", "destination", "security_state", "code_word_commitment")}
    return ChaCha20Poly1305(key).decrypt(nonce, ciphertext, canonical_json(metadata)).decode("utf-8")


def run_demo() -> dict[str, Any]:
    alpha = Office(
        "alpha.telegraph.ww.cx",
        {"secure_message", "rtt_t140", "attachment"},
        {"end_to_end_encryption", "forward_secrecy", "mutual_tls", "signed_receipts", "code_word_commitments"},
        {"bravo.telegraph.ww.cx": "trusted"},
    )
    bravo = Office(
        "bravo.telegraph.ww.cx",
        {"secure_message", "rtt_t140", "attachment"},
        {"end_to_end_encryption", "forward_secrecy", "mutual_tls", "signed_receipts", "code_word_commitments"},
        {"alpha.telegraph.ww.cx": "trusted"},
    )

    envelope, key = encrypt_envelope(alpha, bravo, "Accessible secure test message", "NORTH STAR")
    decision = alpha.route(bravo, {
        "message_id": envelope["message_id"],
        "security": {"end_to_end_encryption", "signed_receipts", "code_word_commitments"},
        "media": {"secure_message", "rtt_t140"},
    })
    if decision["result"] != "selected":
        raise RuntimeError("reference route was unexpectedly rejected")

    now = time.time()
    accepted = bravo.replay_cache.accept(envelope["nonce"], now, 3600)
    if not accepted:
        raise RuntimeError("new envelope was incorrectly classified as replay")
    plaintext = decrypt_envelope(envelope, key)
    first_receipt = bravo.receipt(envelope, "delivered_to_endpoint")

    duplicate_accepted = bravo.replay_cache.accept(envelope["nonce"], now + 1, 3600)
    if duplicate_accepted:
        raise RuntimeError("duplicate envelope bypassed replay protection")
    duplicate_receipt = bravo.receipt(envelope, "duplicate_rejected", duplicate=True)

    return {
        "identity_documents": [alpha.identity_document(), bravo.identity_document()],
        "route_decision": decision,
        "envelope": envelope,
        "decrypted_message": plaintext,
        "receipts": [first_receipt, duplicate_receipt],
        "checks": {
            "route_selected": True,
            "ciphertext_decrypted": plaintext == "Accessible secure test message",
            "code_word_commitment_present": envelope["code_word_commitment"].startswith("sha256:"),
            "replay_rejected": not duplicate_accepted,
            "receipt_chain_linked": duplicate_receipt.get("previous_receipt_digest") == sha256(canonical_json(first_receipt)),
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True))
