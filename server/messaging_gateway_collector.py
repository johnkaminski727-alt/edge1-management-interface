#!/usr/bin/env python3
"""Read-only telemetry collector for the WW.CX messaging gateway.

The collector performs only loopback HTTP GET requests and a read-only
`systemctl is-active` check. It cannot restart services, modify routing, or
send SMS/MMS traffic.
"""

from __future__ import annotations

import json
import subprocess
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from messaging_health_models import MessagingHealthSnapshot, health_snapshot

SERVICE = "wwcx-messaging-gateway.service"
BASE_URL = "http://127.0.0.1:58080"


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


def endpoint_is_healthy(path: str, opener: Callable = urlopen) -> bool:
    request = Request(
        f"{BASE_URL}{path}",
        headers={"User-Agent": "WWCX-read-only-health-probe/1.0"},
        method="GET",
    )
    try:
        with opener(request, timeout=2) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read(4096).decode("utf-8"))
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError):
        return False

    if path == "/healthz":
        return payload.get("status") == "ok"
    if path == "/readyz":
        return payload.get("status") == "ready"
    return False


def collect_gateway_health() -> MessagingHealthSnapshot:
    active = service_is_active()
    reachable = endpoint_is_healthy("/healthz") and endpoint_is_healthy("/readyz")
    return health_snapshot(
        service_active=active,
        listener_reachable=reachable,
    )


if __name__ == "__main__":
    print(json.dumps(collect_gateway_health().to_dict(), indent=2))
