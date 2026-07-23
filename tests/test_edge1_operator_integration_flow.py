"""Integration flow checks for Edge1 Operator components.

These tests verify the adapter, registry, dispatcher, transport, and runtime
layers can be composed into an executable request path.
"""

from server.edge1_operator_dispatch import OperatorDispatcher, OperatorDispatchError
from server.edge1_operator_mcp_adapter import MCPAdapter
from server.edge1_operator_runtime import execution_id
from server.edge1_operator_transport import (
    Edge1OperatorTransport,
    TransportRequest,
)


class Runtime:
    def identity(self):
        return {"service": "edge1-operator"}

    def health(self):
        return {"status": "ok"}


def test_adapter_lists_and_calls_runtime_tools():
    adapter = MCPAdapter(Runtime())

    assert adapter.list_tools() == ["edge1.health", "edge1.identity"]

    identity = adapter.call_tool("edge1.identity")
    assert identity.status == "ok"
    assert identity.payload == {"service": "edge1-operator"}

    unknown = adapter.call_tool("edge1.unknown")
    assert unknown.status == "error"
    assert unknown.payload == {"message": "unknown_tool"}


def test_dispatcher_and_transport_execute_request_path():
    adapter = MCPAdapter(Runtime())
    dispatcher = OperatorDispatcher()
    dispatcher.register(
        "tools/call",
        lambda name, arguments=None: {
            "tool": adapter.call_tool(name, **(arguments or {})).tool,
            "status": adapter.call_tool(name, **(arguments or {})).status,
            "payload": adapter.call_tool(name, **(arguments or {})).payload,
        },
    )
    transport = Edge1OperatorTransport(dispatcher)

    response = transport.handle(
        TransportRequest(
            method="tools/call",
            payload={"name": "edge1.identity", "arguments": {}},
        )
    )

    assert response.ok is True
    assert response.result == {
        "tool": "edge1.identity",
        "status": "ok",
        "payload": {"service": "edge1-operator"},
    }


def test_dispatcher_rejects_unknown_tool():
    dispatcher = OperatorDispatcher()

    try:
        dispatcher.dispatch("missing")
    except OperatorDispatchError as exc:
        assert str(exc) == "unknown tool: missing"
    else:
        raise AssertionError("unknown dispatch must fail")


def test_execution_ids_are_bounded_and_unique():
    first = execution_id()
    second = execution_id()

    assert len(first) == 16
    assert len(second) == 16
    assert first != second
    assert all(character in "0123456789abcdef" for character in first + second)
