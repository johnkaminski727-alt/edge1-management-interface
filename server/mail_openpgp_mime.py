#!/usr/bin/env python3
"""PGP/MIME detection and key-blind transformation contracts.

Private keys are intentionally not handled here. A trusted isolated adapter
returns fully formed PGP/MIME bytes plus bounded fingerprint metadata.
"""
from __future__ import annotations
import hashlib
from email import policy
from email.parser import BytesParser
from typing import Any, Callable

CONTRACT = "wwcx.mail-openpgp-transform.v1"

class OpenPGPMIMEError(RuntimeError):
    pass

def detect(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw:
        raise OpenPGPMIMEError("RFC822 bytes are required")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception as exc:
        raise OpenPGPMIMEError("RFC822 parse failed") from exc
    content_type = message.get_content_type().casefold()
    protocol = str(message.get_param("protocol", header="content-type") or "").casefold()
    encrypted = content_type == "multipart/encrypted" and protocol == "application/pgp-encrypted"
    signed = content_type == "multipart/signed" and protocol == "application/pgp-signature"
    return {
        "pgp_mime": encrypted or signed,
        "encrypted": encrypted,
        "signed": signed,
        "content_type": content_type,
    }

def require_transform(
    plaintext: bytes,
    adapter: Callable[[bytes, dict[str, Any]], dict[str, Any]] | None,
    request: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(plaintext, bytes) or not plaintext:
        raise OpenPGPMIMEError("plaintext MIME bytes are required")
    if adapter is None or not callable(adapter):
        raise OpenPGPMIMEError("isolated OpenPGP adapter is not configured")
    result = adapter(plaintext, request)
    expected = {
        "contract",
        "mime_bytes",
        "operation",
        "signing_fingerprint",
        "recipient_fingerprints",
    }
    if not isinstance(result, dict) or set(result) != expected or result.get("contract") != CONTRACT:
        raise OpenPGPMIMEError("OpenPGP adapter returned an invalid contract")
    mime_bytes = result["mime_bytes"]
    if not isinstance(mime_bytes, bytes) or not mime_bytes:
        raise OpenPGPMIMEError("OpenPGP adapter returned no MIME bytes")
    operation = result["operation"]
    if operation not in {"sign", "encrypt", "sign_encrypt"}:
        raise OpenPGPMIMEError("OpenPGP operation is invalid")
    state = detect(mime_bytes)
    if "encrypt" in operation and not state["encrypted"]:
        raise OpenPGPMIMEError("adapter did not produce PGP/MIME encryption")
    if operation == "sign" and not state["signed"]:
        raise OpenPGPMIMEError("adapter did not produce PGP/MIME signature")
    return {
        "contract": CONTRACT,
        "mime_bytes": mime_bytes,
        "operation": operation,
        "plaintext_sha256": hashlib.sha256(plaintext).hexdigest(),
        "ciphertext_sha256": hashlib.sha256(mime_bytes).hexdigest(),
        "signing_fingerprint": result["signing_fingerprint"],
        "recipient_fingerprints": list(result["recipient_fingerprints"]),
    }
