#!/usr/bin/env python3
"""Explicitly gated SNMP SET execution helper.

This module is intentionally not exposed as an automatic API action. It enforces
both the global configuration gate and the per-device write gate before invoking
Net-SNMP. Callers must still pass through the privileged-network-change policy.
"""
from __future__ import annotations

import re
import subprocess
from typing import Any, Callable

from edge1_snmp_platform import CredentialResolver, canonical_oid, get_device, load_config

_ALLOWED_TYPES = {"i", "u", "t", "a", "o", "s", "x", "d", "b"}


def _redact_error(text: str) -> str:
    return re.sub(
        r"(?i)(community|password|passphrase|authpass|privpass)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )[-4000:]


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
    profile = (resolver or CredentialResolver()).load(device["credential_reference"])
    if profile.version != "3":
        raise PermissionError("SNMP SET credential profile must use SNMPv3")
    argv = [
        "snmpset", "-OQn", "-t", "3", "-r", "1", "-v3", "-l", "authPriv",
        "-u", profile.username or "", "-a", profile.auth_protocol or "SHA",
        "-A", profile.auth_password or "", "-x", profile.priv_protocol or "AES",
        "-X", profile.priv_password or "", f"udp:{device['management_address']}:{device['snmp_port']}",
        oid, value_type, value,
    ]
    try:
        result = runner(
            argv,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "MIBS": ""},
        )
    finally:
        for index in range(len(argv)):
            argv[index] = "[REDACTED]"
    if result.returncode != 0:
        raise RuntimeError(_redact_error(result.stderr or result.stdout or "SNMP SET failed"))
    return {"device_id": device_id, "oid": oid, "status": "succeeded"}
