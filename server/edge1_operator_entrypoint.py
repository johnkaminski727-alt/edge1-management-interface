"""Edge1 Operator service entrypoint.

The service process owns the bounded runtime and protocol dispatcher. The
production MCP transport remains a separate attachment layer; this module does
not open a public listener.
"""
from __future__ import annotations

import time

from .edge1_operator_audit import write_event
from .edge1_operator_dispatch import OperatorDispatcher
from .edge1_operator_mcp_adapter import MCPAdapter
from .edge1_operator_mcp_protocol import PUBLIC_EDGE1_TOOL_NAMES, TOOLS
from .edge1_operator_runtime import Edge1OperatorRuntime
from .edge1_operator_transport import Edge1OperatorTransport
from .edge1_operator_turn_state import TurnStateStore


PUBLIC_EDGE1_TOOL_SET = frozenset(PUBLIC_EDGE1_TOOL_NAMES)


def _tool_result(result):
    return {
        "tool": result.tool,
        "status": result.status,
        "payload": result.payload,
    }


def _call_public_tool(adapter: MCPAdapter, name: str, arguments=None):
    # The adapter intentionally retains newer internal agent.turn.* capabilities
    # for explicitly scoped internal workflows. They are not part of this public
    # Edge1 Operator app. Enforce the public contract again at invocation time so
    # a hand-crafted tools/call cannot bypass tools/list discovery metadata.
    if name not in PUBLIC_EDGE1_TOOL_SET:
        return {
            "tool": name,
            "status": "error",
            "payload": {"message": "unknown_tool"},
        }
    return _tool_result(adapter.call_tool(name, **(arguments or {})))


def build_operator(
    runtime: Edge1OperatorRuntime | None = None,
    turn_store: TurnStateStore | None = None,
):
    runtime = runtime or Edge1OperatorRuntime()
    # TurnStateStore resolves its own durable default root (see
    # edge1_operator_turn_state._default_root) when none is given here. The
    # adapter may use it for internal workflows, but the public dispatcher below
    # exposes only PUBLIC_EDGE1_TOOL_NAMES.
    turn_store = turn_store or TurnStateStore(audit_writer=write_event)
    adapter = MCPAdapter(runtime, turn_store=turn_store)
    dispatcher = OperatorDispatcher()
    dispatcher.register("tools/list", lambda: {"tools": TOOLS})
    dispatcher.register(
        "tools/call",
        lambda name, arguments=None: _call_public_tool(adapter, name, arguments),
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
