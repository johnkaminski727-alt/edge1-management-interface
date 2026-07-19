#!/usr/bin/env python3
"""Edge1 Operator MCP adapter boundary."""

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
            "edge1.health": self.health,
            "edge1.identity": self.identity,
        }

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def call_tool(self, name: str, **kwargs: Any) -> ToolResult:
        handler = self._tools.get(name)
        if handler is None:
            return ToolResult(name, "error", {"message": "unknown_tool"})
        return handler(**kwargs)

    def identity(self, **_: Any) -> ToolResult:
        return ToolResult("edge1.identity", "ok", self.runtime.identity())

    def health(self, **_: Any) -> ToolResult:
        return ToolResult("edge1.health", "ok", self.runtime.health())
