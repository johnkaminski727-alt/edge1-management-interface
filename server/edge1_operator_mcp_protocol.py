#!/usr/bin/env python3
"""Edge1 Operator MCP protocol boundary."""

from __future__ import annotations


TOOLS = [
    {
        "name": "edge1.identity",
        "description": "Return verified Edge1 operator identity information.",
        "inputSchema": {"type": "object"},
    },
    {
        "name": "edge1.health",
        "description": "Return Edge1 operator health information.",
        "inputSchema": {"type": "object"},
    },
]
