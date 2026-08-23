#!/usr/bin/env python3
"""Read-only telemetry collector for the WW.CX messaging gateway.

The collector performs only loopback HTTP GET requests, fixed filesystem metadata
checks, a fixed scanner-version probe, and a read-only ``systemctl is-active``
check. It cannot restart services, inspect message content, release quarantine,
modify routing, or send SMS/MMS traffic.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from messaging_health_models import MessagingHealthSnapshot, health_snapshot

SERVICE = "wwcx-messaging-gateway.service"
BASE_URL = "http://127.0.0.1:58080"
QUARANTINE_ROOT = Path("/var/lib/wwcx-messaging-gateway/private-mms-quarantine")
CLAMSCAN = Path("/usr/bin/clamscan")


def service_is_active() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", SERVICE],
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def endpoint_payload(path: str, opener: Callable = urlopen) -> dict[str, object] | None:
    if path not in {"/healthz", "/readyz"}:
        return None
    request = Request(
        f"{BASE_URL}{path}",
        headers={"User-Agent": "WWCX-read-only-health-probe/1.0"},
        method="GET",
    )
    try:
        with opener(request, timeout=2) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read(4096).decode("utf-8"))
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def endpoint_is_healthy(path: str, opener: Callable = urlopen) -> bool:
    payload = endpoint_payload(path, opener=opener)
    if payload is None:
        return False
    if path == "/healthz":
        return payload.get("status") == "ok"
    if path == "/readyz":
        return payload.get("status") == "ready"
    return False


def quarantine_root_status(root: Path = QUARANTINE_ROOT) -> tuple[bool, bool]:
    """Return presence and strict owner-only-directory posture without reading files."""
    try:
        metadata = root.lstat()
    except (FileNotFoundError, PermissionError, OSError):
        return False, False
    present = stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode)
    secure = present and stat.S_IMODE(metadata.st_mode) == 0o700
    return present, secure


def trusted_scanner_status(
    path: Path = CLAMSCAN,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, str]:
    """Probe only the fixed local clamscan binary and return a bounded version string."""
    if not path.is_file() or not os.access(path, os.X_OK):
        return False, "unavailable"
    try:
        result = runner(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return False, "unavailable"
    if result.returncode != 0:
        return False, "unavailable"
    first_line = (result.stdout or "").splitlines()[:1]
    version = first_line[0].strip()[:128] if first_line else "available"
    return True, version or "available"


def collect_gateway_health() -> MessagingHealthSnapshot:
    active = service_is_active()
    health = endpoint_payload("/healthz")
    readiness = endpoint_payload("/readyz")
    reachable = bool(
        health
        and health.get("status") == "ok"
        and readiness
        and readiness.get("status") == "ready"
    )
    storage_backend = (
        str(readiness.get("storage", "unknown"))[:32]
        if readiness is not None
        else "unknown"
    )
    quarantine_present, quarantine_secure = quarantine_root_status()
    scanner_available, scanner_version = trusted_scanner_status()
    return health_snapshot(
        service_active=active,
        listener_reachable=reachable,
        storage_backend=storage_backend,
        mms_quarantine_root_present=quarantine_present,
        mms_quarantine_root_secure=quarantine_secure,
        trusted_scanner_available=scanner_available,
        trusted_scanner_version=scanner_version,
    )


if __name__ == "__main__":
    print(json.dumps(collect_gateway_health().to_dict(), indent=2))
