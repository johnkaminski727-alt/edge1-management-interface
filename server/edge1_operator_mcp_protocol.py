#!/usr/bin/env python3
"""Static public MCP tool contract for the Edge1 Operator app."""
from __future__ import annotations


READ_ONLY_LOCAL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "openWorldHint": False,
    "idempotentHint": True,
}
BOUNDED_WRITE_LOCAL_ANNOTATIONS = {
    "readOnlyHint": False,
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


def _telephony_reload_tool() -> dict:
    return {
        "name": "edge1.telephony_console_reload",
        "description": (
            "Restart only the loopback read-only Telephony Console after exact PID, "
            "source-digest and repository-HEAD preconditions. Does not restart Asterisk "
            "or the Messaging Gateway and does not generate traffic."
        ),
        "access": "write",
        "annotations": dict(BOUNDED_WRITE_LOCAL_ANNOTATIONS),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "expected_pid",
                "expected_source_sha256",
                "expected_repo_head",
                "idempotency_key"
            ],
            "properties": {
                "expected_pid": {"type": "integer", "minimum": 1},
                "expected_source_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "expected_repo_head": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                "idempotency_key": {
                    "type": "string",
                    "minLength": 16,
                    "maxLength": 128,
                    "pattern": "^[A-Za-z0-9._:-]+$"
                }
            }
        },
    }


# Public host-control tools are deliberately separate from internal agent.turn.*
# coordination tools. Adding an internal tool to an adapter does not publish it here.
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
    "edge1.ava_office_status",
    "edge1.number_portability_status",
    "edge1.asterisk_status",
    "edge1.telephony_status",
    "edge1.telephony_console_control_status",
    "edge1.telephony_console_reload",
    "edge1.messaging_status",
    "edge1.time_authority_status",
    "edge1.git_state",
    "edge1.config_digest",
    "edge1.capabilities",
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
    _public_read_tool("edge1.ava_office_status", "Return bounded Ava Office health and aggregate read-only summary."),
    _public_read_tool("edge1.number_portability_status", "Return bounded Number Portability health and aggregate read-only summary."),
    _public_read_tool("edge1.asterisk_status", "Return fixed read-only Asterisk diagnostics."),
    _public_read_tool("edge1.telephony_status", "Return bounded telephony console status."),
    _public_read_tool(
        "edge1.telephony_console_control_status",
        "Return sanitized Telephony Console PID/source/repository preconditions for a bounded reload."
    ),
    _telephony_reload_tool(),
    _public_read_tool("edge1.messaging_status", "Return bounded messaging health."),
    _public_read_tool("edge1.time_authority_status", "Return bounded WW.CX time-authority summary."),
    _public_read_tool("edge1.git_state", "Return repository dirty/head state without fetching or changing branches."),
    _public_read_tool("edge1.config_digest", "Return SHA-256 digests for selected repository-controlled operator configuration."),
    _public_read_tool("edge1.capabilities", "Return the sanitized versioned operator capability manifest and effective scope presence."),
]

if tuple(tool["name"] for tool in TOOLS) != PUBLIC_EDGE1_TOOL_NAMES:
    raise RuntimeError("Edge1 Operator public MCP tool contract drift")
