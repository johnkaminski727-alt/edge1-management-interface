#!/usr/bin/env python3
"""Static MCP tool contract for the Edge1 Operator."""
from __future__ import annotations


def _tool(name: str, description: str, access: str = "read", input_schema: dict | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "access": access,
        "inputSchema": input_schema or {"type": "object", "properties": {}, "additionalProperties": False},
    }


TOOLS = [
    _tool("edge1.identity", "Return verified Edge1 operator identity information."),
    _tool("edge1.health", "Return operator and loopback Operations API health."),
    _tool("edge1.snapshot", "Collect one deterministic read-only Edge1 host snapshot through the audited Operations API."),
    _tool("edge1.inventory", "Run the deterministic read-only Edge1 inventory and return its audited result."),
    _tool("edge1.services", "Return bounded running/failed service state."),
    _tool("edge1.network_state", "Return bounded interface, route, and classified listener state."),
    _tool("edge1.disk_state", "Return bounded filesystem usage for approved Edge1 filesystems."),
    _tool("edge1.bigbird_status", "Return bounded BigBird health and tool-registry state."),
    _tool("edge1.operations_status", "Return loopback Operations API health."),
    _tool("edge1.apache_status", "Return bounded Apache service state."),
    _tool("edge1.asterisk_status", "Return fixed read-only Asterisk diagnostics."),
    _tool("edge1.telephony_status", "Return bounded telephony console status."),
    _tool("edge1.messaging_status", "Return bounded messaging health."),
    _tool("edge1.time_authority_status", "Return bounded WW.CX time-authority summary."),
    _tool("edge1.git_state", "Return repository dirty/head state without fetching or changing branches."),
    _tool("edge1.config_digest", "Return SHA-256 digests for selected repository-controlled operator configuration."),
    _tool(
        "agent.turn.status",
        "Return authoritative turn-ownership state for a task/conversation.",
        access="read",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "conversation_id": {"type": "string"},
            },
            "required": ["task_id", "conversation_id"],
            "additionalProperties": False,
        },
    ),
    _tool(
        "agent.turn.handoff",
        "Explicitly transfer turn ownership for a task/conversation. Requires "
        "the current owner, matching epoch, and an idempotency key. Does not "
        "invoke BigBird and does not perform automatic timeout transfer.",
        access="controlled_write",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "conversation_id": {"type": "string"},
                "requesting_agent": {"type": "string"},
                "to_agent": {"type": "string"},
                "expected_epoch": {"type": "integer"},
                "idempotency_key": {"type": "string"},
                "reason": {"type": "string"},
                "evidence": {"type": "string"},
            },
            "required": [
                "task_id",
                "conversation_id",
                "requesting_agent",
                "to_agent",
                "expected_epoch",
                "idempotency_key",
            ],
            "additionalProperties": False,
        },
    ),
]
