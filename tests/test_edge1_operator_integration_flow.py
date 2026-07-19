"""Integration flow checks for Edge1 Operator components.

These tests verify the adapter, registry, dispatcher, transport, and runtime
layers can be composed into an executable request path.
"""

from server.edge1_operator_dispatch import OperatorDispatcher
from server.edge1_operator_mcp_adapter import MCPAdapter
from server.edge1_operator_runtime import execution_id
from server.edge1_operator_transport import (
    Edge1OperatorTransport,
    TransportRequest,
)


class Runtime:
    def identity(self):
        return {"service": "edge1-operator"}



def