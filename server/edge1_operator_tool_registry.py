"""Edge1 Operator MCP-visible tool registry.

Derived from the static protocol contract so registry and protocol cannot
drift apart. Access level comes from each tool's own declared "access"
field (defaulting to "read") rather than being hardcoded here.
"""
from __future__ import annotations

from .edge1_operator_mcp_protocol import TOOLS as PROTOCOL_TOOLS


TOOLS = {
    item["name"]: {
        "access": item.get("access", "read"),
        "description": item["description"],
        "inputSchema": item["inputSchema"],
    }
    for item in PROTOCOL_TOOLS
}


def list_tools():
    return TOOLS
