#!/usr/bin/env python3
"""Retired installer retained only as a fail-closed compatibility marker.

The Ava gateway no longer uses the 0.3.x patch-on-live integration path.
MCP operator access is native in services/bigbird-ai-gateway/app/main.py and is
commissioned through deploy/ava-operator-broker plus the normal gateway deploy.
"""
from __future__ import annotations
import sys


def main() -> int:
    print(
        "RETIRED: Ava MCP operator integration is native in gateway 0.4.3+. "
        "Do not apply the legacy 0.3.x gateway patcher.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
