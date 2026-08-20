#!/usr/bin/env python3
"""Static public MCP tool contract for the Edge1 Operator app."""
from __future__ import annotations


READ_ONLY_LOCAL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "openWorldHint": False,
    "idempotentHint": True,
}


def _public_read_tool(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "access": "read",
        "annotations": dict(READ_ONLY_LOCAL_ANNOTATIONS),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    }


# This tuple is the externally published Edge1 Operator contract. New protocol or
# agent-coordination tools must not be added here merely because they exist in the
# repository; they require a separately reviewed app/tool surface.
PUBLIC_EDGE1_TOOL_NAMES = (
    "edge1.identity",
    "edge1.health",
    "edge1.snapshot",
    "edge1.inventory",
    "edge1.services",
    "edge1.network_state",
    "edge1.disk_state",
    "edge1.bigbird_status",
    "edge1.operations_status",
    "edge1.apache_status",
    "edge1.asterisk_status",
    "edge1.telephony_status",
    "edge1.messaging_status",
    "edge1.time_authority_status",
    "edge1.git_state",
    "edge1.config_digest",
)


TOOLS = [
    _public_read_tool("edge1.identity", "Return verified Edge1 operator identity information."),
    _public_read_tool("edge1.health", "Return operator and loopback Operations API health."),
    _public_read_tool("edge1.snapshot", "Collect one deterministic read-only Edge1 host snapshot through the audited Operations API."),
    _public_read_tool("edge1.inventory", "Run the deterministic read-only Edge1 inventory and return its audited result."),
    _public_read_tool("edge1.services", "Return bounded running/failed service state."),
    _public_read_tool("edge1.network_state", "Return bounded interface, route, and classified listener state."),
    _public_read_tool("edge1.disk_state", "Return bounded filesystem usage for approved Edge1 filesystems."),
    _public_read_tool("edge1.bigbird_status", "Return bounded BigBird health and tool-registry state."),
    _public_read_tool("edge1.operations_status", "Return loopback Operations API health."),
    _public_read_tool("edge1.apache_status", "Return bounded Apache service state."),
    _public_read_tool("edge1.asterisk_status", "Return fixed read-only Asterisk diagnostics."),
    _public_read_tool("edge1.telephony_status", "Return bounded telephony console status."),
    _public_read_tool("edge1.messaging_status", "Return bounded messaging health."),
    _public_read_tool("edge1.time_authority_status", "Return bounded WW.CX time-authority summary."),
    _public_read_tool("edge1.git_state", "Return repository dirty/head state without fetching or changing branches."),
    _public_read_tool("edge1.config_digest", "Return SHA-256 digests for selected repository-controlled operator configuration."),
]

if tuple(tool["name"] for tool in TOOLS) != PUBLIC_EDGE1_TOOL_NAMES:
    raise RuntimeError("Edge1 Operator public MCP tool contract drift")
