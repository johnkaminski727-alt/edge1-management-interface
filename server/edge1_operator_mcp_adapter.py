#!/usr/bin/env python3
"""Edge1 Operator MCP adapter exposing named, read-only capabilities.

Turn-ownership tools (agent.turn.status, agent.turn.handoff) are the only
tools that accept parameters; every other tool remains strictly
parameterless, preserving the existing contract exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .edge1_operator_turn_state import (
    IdempotencyConflictError,
    StaleEpochError,
    UnauthorizedOwnerError,
    UnknownTurnError,
)


@dataclass(frozen=True)
class ToolResult:
    tool: str
    status: str
    payload: dict[str, Any]


class MCPAdapter:
    def __init__(self, runtime: Any, turn_store: Any = None):
        self.runtime = runtime
        self.turn_store = turn_store
        self._tools: dict[str, Callable[..., ToolResult]] = {
            "edge1.identity": self.identity,
            "edge1.health": self.health,
            "edge1.snapshot": self.snapshot,
            "edge1.inventory": self.inventory,
            "edge1.services": self.services,
            "edge1.network_state": self.network_state,
            "edge1.disk_state": self.disk_state,
            "edge1.bigbird_status": self.bigbird_status,
            "edge1.operations_status": self.operations_status,
            "edge1.apache_status": self.apache_status,
            "edge1.asterisk_status": self.asterisk_status,
            "edge1.telephony_status": self.telephony_status,
            "edge1.messaging_status": self.messaging_status,
            "edge1.time_authority_status": self.time_authority_status,
            "edge1.git_state": self.git_state,
            "edge1.config_digest": self.config_digest,
            "agent.turn.status": self.turn_status,
            "agent.turn.handoff": self.turn_handoff,
        }
        self._parameterized_tools = {"agent.turn.status", "agent.turn.handoff"}

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def call_tool(self, name: str, **kwargs: Any) -> ToolResult:
        handler = self._tools.get(name)
        if handler is None:
            return ToolResult(name, "error", {"message": "unknown_tool"})
        accepts_params = name in self._parameterized_tools
        if kwargs and not accepts_params:
            return ToolResult(name, "error", {"message": "parameters_not_accepted"})
        try:
            return handler(**kwargs) if accepts_params else handler()
        except Exception:
            return ToolResult(name, "error", {"message": "runtime_error"})

    def _call(self, tool: str, method: str) -> ToolResult:
        return ToolResult(tool, "ok", getattr(self.runtime, method)())

    def identity(self) -> ToolResult:
        return self._call("edge1.identity", "identity")

    def health(self) -> ToolResult:
        return self._call("edge1.health", "health")

    def snapshot(self) -> ToolResult:
        return self._call("edge1.snapshot", "snapshot")

    def inventory(self) -> ToolResult:
        return self._call("edge1.inventory", "inventory")

    def services(self) -> ToolResult:
        return self._call("edge1.services", "services")

    def network_state(self) -> ToolResult:
        return self._call("edge1.network_state", "network_state")

    def disk_state(self) -> ToolResult:
        return self._call("edge1.disk_state", "disk_state")

    def bigbird_status(self) -> ToolResult:
        return self._call("edge1.bigbird_status", "bigbird_status")

    def operations_status(self) -> ToolResult:
        return self._call("edge1.operations_status", "operations_status")

    def apache_status(self) -> ToolResult:
        return self._call("edge1.apache_status", "apache_status")

    def asterisk_status(self) -> ToolResult:
        return self._call("edge1.asterisk_status", "asterisk_status")

    def telephony_status(self) -> ToolResult:
        return self._call("edge1.telephony_status", "telephony_status")

    def messaging_status(self) -> ToolResult:
        return self._call("edge1.messaging_status", "messaging_status")

    def time_authority_status(self) -> ToolResult:
        return self._call("edge1.time_authority_status", "time_authority_status")

    def git_state(self) -> ToolResult:
        return self._call("edge1.git_state", "git_state")

    def config_digest(self) -> ToolResult:
        return self._call("edge1.config_digest", "config_digest")

    def turn_status(self, task_id: str, conversation_id: str) -> ToolResult:
        if self.turn_store is None:
            return ToolResult("agent.turn.status", "error", {"message": "turn_store_unavailable"})
        try:
            data = self.turn_store.status(task_id, conversation_id)
            return ToolResult("agent.turn.status", "ok", data)
        except UnknownTurnError:
            return ToolResult("agent.turn.status", "error", {"message": "unknown_task_conversation"})

    def turn_handoff(
        self,
        task_id: str,
        conversation_id: str,
        requesting_agent: str,
        to_agent: str,
        expected_epoch: int,
        idempotency_key: str,
        reason: str | None = None,
        evidence: str | None = None,
    ) -> ToolResult:
        if self.turn_store is None:
            return ToolResult("agent.turn.handoff", "error", {"message": "turn_store_unavailable"})
        try:
            data = self.turn_store.handoff(
                task_id=task_id,
                conversation_id=conversation_id,
                requesting_agent=requesting_agent,
                to_agent=to_agent,
                expected_epoch=expected_epoch,
                idempotency_key=idempotency_key,
                reason=reason,
                evidence=evidence,
            )
            return ToolResult("agent.turn.handoff", "ok", data)
        except UnknownTurnError:
            return ToolResult("agent.turn.handoff", "error", {"message": "unknown_task_conversation"})
        except UnauthorizedOwnerError:
            return ToolResult("agent.turn.handoff", "error", {"message": "unauthorized_owner"})
        except StaleEpochError:
            return ToolResult("agent.turn.handoff", "error", {"message": "stale_epoch"})
        except IdempotencyConflictError:
            return ToolResult("agent.turn.handoff", "error", {"message": "idempotency_conflict"})
