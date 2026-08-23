#!/usr/bin/env python3
"""Emit sanitized carrier configuration readiness without activating a provider."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.provider_readiness import sanitized_provider_readiness
from app.providers import build_provider_registry


def main() -> int:
    active = build_provider_registry(lambda: "readiness-probe-does-not-use-simulator-token")
    payload = sanitized_provider_readiness(
        os.environ,
        registered_providers=set(active),
    )
    payload["active_provider_names"] = sorted(active)
    payload["activation_performed"] = False
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
