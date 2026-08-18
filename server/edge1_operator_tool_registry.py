"""Edge1 Operator MCP-visible tool registry.

Only named read-only capabilities are exposed here. Mutating operations remain
separate Operations API actions and are not surfaced as a generic MCP exec tool.
"""
from __future__ import annotations

from .edge1_operator_mcp_protocol import TOOLS as PROTOCOL_TOOLS


TOOLS = {
    item["name"]: {
        "access": "read",
        "description": item["description"],
        "inputSchema": item["inputSchema"],
    }
    for item in PROTOCOL_TOOLS
}


def list_tools():
    return TOOLS
