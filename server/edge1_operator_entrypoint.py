"""Edge1 Operator service entrypoint.

The service process owns the bounded runtime and protocol dispatcher. The
production MCP transport remains a separate attachment layer; this module does
not open a public listener.
"""
from __future__ import annotations

import time

from .edge1_operator_dispatch import OperatorDispatcher
from .edge1_operator_mcp_adapter import MCPAdapter
from .edge1_operator_mcp_protocol import TOOLS
from .edge1_operator_runtime import Edge1OperatorRuntime
from .edge1_operator_transport import Edge1OperatorTransport


def _tool_result(result):
    return {
        "tool": result.tool,
        "status": result.status,
        "payload": result.payload,
    }


def build_operator(runtime: Edge1OperatorRuntime | None = None):
    runtime = runtime or Edge1OperatorRuntime()
    adapter = MCPAdapter(runtime)
    dispatcher = OperatorDispatcher()
    dispatcher.register("tools/list", lambda: {"tools": TOOLS})
    dispatcher.register(
        "tools/call",
        lambda name, arguments=None: _tool_result(
            adapter.call_tool(name, **(arguments or {}))
        ),
    )
    transport = Edge1OperatorTransport(dispatcher)
    return transport, runtime


def main() -> int:
    _operator, runtime = build_operator()
    runtime.health()

    while True:
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
