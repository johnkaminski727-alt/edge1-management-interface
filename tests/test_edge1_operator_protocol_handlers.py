#!/usr/bin/env python3
"""Protocol handler smoke tests for Edge1 Operator."""

from server.edge1_operator_protocol import Edge1OperatorProtocol


def test_protocol_registers_tools():
    protocol = Edge1OperatorProtocol()
    assert protocol.tools()


def test_unknown_tool_is_rejected():
    protocol = Edge1OperatorProtocol()
    result = protocol.call("missing", {})
    assert result["ok"] is False
