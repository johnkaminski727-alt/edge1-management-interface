#!/usr/bin/env python3
"""Secure Net-SNMP client execution without passphrases in process arguments.

Net-SNMP documents command-line passphrases as insecure and supports equivalent
SNMPv3 defaults in a user-readable-only snmp.conf. This wrapper creates a
mode-0600 ephemeral configuration in a mode-0700 temporary directory, points
SNMPCONFPATH only at that directory, invokes a fixed Net-SNMP binary, then
removes the configuration immediately.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from edge1_snmp_platform import CredentialResolver, DEFAULT_RETRIES, DEFAULT_TIMEOUT

_ALLOWED_QUERY_TOOLS = {"snmpget", "snmpwalk", "snmpbulkwalk"}
_ALLOWED_SET_TYPES = {"i", "u", "t", "a", "o", "s", "x", "d", "b"}


def _quoted(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Net-SNMP credential fields cannot contain control characters")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _algorithm(value: str, label: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,32}", value):
        raise ValueError(f"invalid {label} algorithm")
    return value


def _profile_config(profile) -> str:
    if profile.version == "3":
        return "\n".join([
            "defVersion 3",
            f"defSecurityName {_quoted(profile.username or '')}",
            "defSecurityLevel authPriv",
            f"defAuthType {_algorithm(profile.auth_protocol or 'SHA', 'authentication')}",
            f"defAuthPassphrase {_quoted(profile.auth_password or '')}",
            f"defPrivType {_algorithm(profile.priv_protocol or 'AES', 'privacy')}",
            f"defPrivPassphrase {_quoted(profile.priv_password or '')}",
            "",
        ])
    if profile.version in {"1", "2c"}:
        return "\n".join([
            f"defVersion {profile.version}",
            f"defCommunity {_quoted(profile.community or '')}",
            "",
        ])
    raise ValueError("unsupported credential profile")


def _safe_error(text: str) -> str:
    return re.sub(
        r"(?i)(community|password|passphrase|authpass|privpass)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )[-4000:]


class SecureNetSNMP:
    def __init__(self, resolver: CredentialResolver | None = None, *, runner: Callable[..., Any] = subprocess.run):
        self.resolver = resolver or CredentialResolver()
        self.runner = runner

    def _run(self, tool: str, address: str, port: int, profile_ref: str, tail: list[str], *, timeout: int, retries: int):
        if tool not in _ALLOWED_QUERY_TOOLS | {"snmpset"}:
            raise ValueError("unsupported Net-SNMP tool")
        profile = self.resolver.load(profile_ref)
        with tempfile.TemporaryDirectory(prefix="edge1-snmp-") as directory:
            os.chmod(directory, 0o700)
            conf = Path(directory) / "snmp.conf"
            conf.write_text(_profile_config(profile), encoding="utf-8")
            os.chmod(conf, 0o600)
            argv = [tool, "-OQn", "-t", str(timeout), "-r", str(retries), f"udp:{address}:{int(port)}", *tail]
            env = {
                "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                "MIBS": "",
                "SNMPCONFPATH": directory,
                "HOME": directory,
            }
            completed = self.runner(
                argv,
                text=True,
                capture_output=True,
                timeout=max(5, timeout * (retries + 2)),
                check=False,
                env=env,
            )
        if completed.returncode != 0:
            raise RuntimeError(_safe_error(completed.stderr or completed.stdout or "Net-SNMP operation failed"))
        return completed

    def query(self, tool: str, address: str, port: int, profile_ref: str, oids: list[str], *, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> dict[str, str]:
        if tool not in _ALLOWED_QUERY_TOOLS:
            raise ValueError("unsupported Net-SNMP query tool")
        completed = self._run(tool, address, port, profile_ref, list(oids), timeout=timeout, retries=retries)
        result: dict[str, str] = {}
        for line in completed.stdout.splitlines():
            if "=" in line:
                oid, value = line.split("=", 1)
                result[oid.strip().lstrip(".")] = value.strip()
        return result

    def set_value(self, address: str, port: int, profile_ref: str, oid: str, value_type: str, value: str, *, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> None:
        if value_type not in _ALLOWED_SET_TYPES:
            raise ValueError("unsupported Net-SNMP SET value type")
        self._run("snmpset", address, port, profile_ref, [oid, value_type, value], timeout=timeout, retries=retries)
