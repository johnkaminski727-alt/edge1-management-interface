#!/usr/bin/env python3
"""Explicitly gated SNMP SET execution helper.

This module is intentionally not exposed as an automatic API action. It enforces
both the global configuration gate and the per-device write gate before invoking
Net-SNMP. Callers must still pass through the privileged-network-change policy.
Passphrases are supplied through the secure ephemeral snmp.conf execution path,
not process arguments.
"""
from __future__ import annotations

import subprocess
from typing import Any, Callable

from edge1_snmp_platform import CredentialResolver, canonical_oid, get_device, load_config
from edge1_snmp_secure_exec import SecureNetSNMP

_ALLOWED_TYPES = {"i", "u", "t", "a", "o", "s", "x", "d", "b"}


def execute_set(
    conn,
    *,
    device_id: str,
    oid: str,
    value_type: str,
    value: str,
    config: dict[str, Any] | None = None,
    resolver: CredentialResolver | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    config = config or load_config()
    if not bool(config.get("snmp_set_enabled", False)):
        raise PermissionError("SNMP SET is globally disabled")
    device = get_device(conn, device_id)
    if not bool(device.get("write_enabled")):
        raise PermissionError("SNMP SET is disabled for this device")
    if device.get("snmp_version") != "3":
        raise PermissionError("SNMP SET requires SNMPv3 in this implementation")
    if value_type not in _ALLOWED_TYPES:
        raise ValueError("unsupported Net-SNMP SET value type")
    oid = canonical_oid(oid)
    credential_resolver = resolver or CredentialResolver()
    profile = credential_resolver.load(device["credential_reference"])
    if profile.version != "3":
        raise PermissionError("SNMP SET credential profile must use SNMPv3")
    SecureNetSNMP(credential_resolver, runner=runner).set_value(
        device["management_address"],
        int(device["snmp_port"]),
        device["credential_reference"],
        oid,
        value_type,
        value,
    )
    return {"device_id": device_id, "oid": oid, "status": "succeeded"}
