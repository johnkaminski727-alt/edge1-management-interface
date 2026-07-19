"""Edge1 Operator service entrypoint."""

from __future__ import annotations

import time

from .edge1_operator_dispatch import OperatorDispatcher
from .edge1_operator_mcp_adapter import MCPAdapter
from .edge1_operator_runtime import Edge1OperatorRuntime
from .edge1_operator_transport import Edge1OperatorTransport


def build_operator():
    runtime = Edge1OperatorRuntime()
    adapter = MCPAdapter(runtime)
    dispatcher = OperatorDispatcher(adapter)
    transport = Edge1OperatorTransport(dispatcher)
    return transport, runtime


def main() -> int:
    operator, runtime = build_operator()

    runtime.health()

    while True:
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
