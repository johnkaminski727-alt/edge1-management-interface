#!/usr/bin/env python3
"""Fail-closed OpenPGP policy contract for WW.CX mail.

No private key material is handled here. The module validates policy and resolves
whether a recipient may receive plaintext, signed, or encrypted PGP/MIME mail.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

CONTRACT = "wwcx.mail-openpgp-policy.v1"
MODES = {"disabled", "sign_only", "encrypt_if_verified_key", "require_encryption"}

class OpenPGPPolicyError(ValueError):
    pass

@dataclass(frozen=True)
class RecipientKey:
    address: str
    fingerprint: str
    verified: bool
    revoked: bool = False
    expired: bool = False

    def usable(self) -> bool:
        fp = "".join(self.fingerprint.split()).upper()
        return (
            self.verified
            and not self.revoked
            and not self.expired
            and len(fp) in {40, 64}
            and all(c in "0123456789ABCDEF" for c in fp)
        )

def validate_policy(p: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(p, dict) or p.get("contract") != CONTRACT:
        raise OpenPGPPolicyError("unsupported OpenPGP policy")
    if p.get("format") != "pgp_mime":
        raise OpenPGPPolicyError("only PGP/MIME is supported")
    if p.get("default_mode") not in MODES:
        raise OpenPGPPolicyError("invalid default OpenPGP mode")
    if set(p.get("allowed_modes", [])) != MODES:
        raise OpenPGPPolicyError("allowed OpenPGP modes are incomplete")
    keys = p.get("keys") or {}
    outbound = p.get("outbound") or {}
    inbound = p.get("inbound") or {}
    audit = p.get("audit") or {}
    if (
        keys.get("private_key_export_prohibited") is not True
        or keys.get("ai_private_key_access") is not False
        or keys.get("application_private_key_access") is not False
    ):
        raise OpenPGPPolicyError("private-key isolation policy is unsafe")
    if keys.get("allow_keyserver_autofetch") is not False or keys.get("allow_wkd_autofetch") is not False:
        raise OpenPGPPolicyError("automatic public-key discovery is not permitted")
    if outbound.get("scan_plaintext_before_encryption") is not True or outbound.get("require_clean_plaintext_scan") is not True:
        raise OpenPGPPolicyError("encrypted outbound mail must be scanned before encryption")
    if outbound.get("never_encrypt_without_verified_recipient_key") is not True or outbound.get("refuse_plaintext_when_encryption_required") is not True:
        raise OpenPGPPolicyError("recipient-key fail-closed policy is incomplete")
    if inbound.get("preserve_encrypted_original") is not True or audit.get("record_private_key_material") is not False:
        raise OpenPGPPolicyError("OpenPGP retention/audit policy is unsafe")
    return p

def resolve_mode(
    policy: dict[str, Any],
    requested_mode: str | None,
    recipient_keys: list[RecipientKey],
    recipient_count: int,
) -> dict[str, Any]:
    validate_policy(policy)
    mode = (requested_mode or policy["default_mode"]).strip()
    if mode not in MODES or mode not in policy["allowed_modes"]:
        raise OpenPGPPolicyError("requested OpenPGP mode is not allowed")
    if recipient_count < 1:
        raise OpenPGPPolicyError("recipient count is invalid")
    usable = [key for key in recipient_keys if key.usable()]
    if mode == "disabled":
        return {"mode": mode, "encrypt": False, "sign": False, "fingerprints": []}
    if mode == "sign_only":
        if not policy["outbound"]["sign_enabled"]:
            raise OpenPGPPolicyError("OpenPGP signing is not enabled")
        return {"mode": mode, "encrypt": False, "sign": True, "fingerprints": []}
    if len(usable) != recipient_count:
        if mode == "require_encryption":
            raise OpenPGPPolicyError("verified recipient OpenPGP key is required")
        return {
            "mode": mode,
            "encrypt": False,
            "sign": bool(policy["outbound"]["sign_enabled"]),
            "fingerprints": [],
        }
    if not policy["outbound"]["encrypt_enabled"]:
        raise OpenPGPPolicyError("OpenPGP encryption is not enabled")
    return {
        "mode": mode,
        "encrypt": True,
        "sign": bool(policy["outbound"]["sign_enabled"]),
        "fingerprints": ["".join(key.fingerprint.split()).upper() for key in usable],
    }
