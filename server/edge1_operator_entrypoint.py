"""Edge1 Operator service entrypoint.

The service process owns the bounded runtime and protocol dispatcher. The
production MCP transport remains a separate attachment layer; this module does
not open a public listener.
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from .edge1_operator_audit import write_event
from .edge1_operator_dispatch import OperatorDispatcher
from .edge1_operator_mcp_adapter import MCPAdapter
from .edge1_operator_mcp_protocol import TOOLS
from .edge1_operator_runtime import Edge1OperatorRuntime
from .edge1_operator_transport import Edge1OperatorTransport
from .edge1_operator_turn_state import TurnStateStore


def _tool_result(result):
    return {
        "tool": result.tool,
        "status": result.status,
        "payload": result.payload,
    }


def _default_turn_state_root() -> str:
    # A relative repo-local path is not safe to default to: directories like
    # var/ here are root-owned and not writable by the service account or by
    # test runs. Fall back to the system temp dir, which is writable in any
    # environment (dev, tests, CI). Production deployment should set
    # EDGE1_OPERATOR_TURN_STATE_ROOT explicitly to a dedicated, properly
    # permissioned path -- that is a deployment decision, out of scope here.
    configured = os.environ.get("EDGE1_OPERATOR_TURN_STATE_ROOT")
    if configured:
        return configured
    return str(Path(tempfile.gettempdir()) / "edge1-operator-turn-state")


def build_operator(
    runtime: Edge1OperatorRuntime | None = None,
    turn_store: TurnStateStore | None = None,
):
    runtime = runtime or Edge1OperatorRuntime()
    turn_store = turn_store or TurnStateStore(
        root=_default_turn_state_root(),
        audit_writer=write_event,
    )
    adapter = MCPAdapter(runtime, turn_store=turn_store)
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
