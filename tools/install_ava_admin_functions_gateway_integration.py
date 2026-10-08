#!/usr/bin/env python3
"""Retired installer retained only as a fail-closed compatibility marker.

Administrator-controlled shell gates and bounded actions are now consumed by
the native 0.4.3+ Ava MCP gateway and the AVA Executive dispatcher. This old
0.3.x live-patching installer must not be used.
"""
from __future__ import annotations
import sys


def main() -> int:
    print(
        "RETIRED: Ava admin/MCP integration is native in gateway 0.4.3+. "
        "Do not apply the legacy 0.3.x gateway patcher.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
