#!/usr/bin/env python3
"""Edge1 Operator MCP adapter exposing named, read-only capabilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolResult:
    tool: str
    status: str
    payload: dict[str, Any]


class MCPAdapter:
    def __init__(self, runtime: Any):
        self.runtime = runtime
        self._tools: dict[str, Callable[..., ToolResult]] = {
            "edge1.identity": self.identity,
            "edge1.health": self.health,
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
        }

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def call_tool(self, name: str, **kwargs: Any) -> ToolResult:
        handler = self._tools.get(name)
        if handler is None:
            return ToolResult(name, "error", {"message": "unknown_tool"})
        if kwargs:
            return ToolResult(name, "error", {"message": "parameters_not_accepted"})
        try:
            return handler()
        except Exception:
            return ToolResult(name, "error", {"message": "runtime_error"})

    def _call(self, tool: str, method: str) -> ToolResult:
        return ToolResult(tool, "ok", getattr(self.runtime, method)())

    def identity(self) -> ToolResult:
        return self._call("edge1.identity", "identity")

    def health(self) -> ToolResult:
        return self._call("edge1.health", "health")

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
