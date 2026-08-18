#!/usr/bin/env python3
"""Compatibility status entrypoint for the bounded Edge1 Operator.

Historical revisions exposed a generic ``run_bounded(command)`` helper here.
That helper is intentionally removed: MCP-visible authority is now limited to
named, parameterless tools backed by the hardened loopback Operations API.
"""
from __future__ import annotations

import json

from .edge1_operator_entrypoint import build_operator


def main() -> None:
    operator, runtime = build_operator()
    tools = operator.dispatcher.dispatch("tools/list")
    print(
        json.dumps(
            {
                "status": "ready",
                "identity": runtime.identity(),
                "tools": tools["tools"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
