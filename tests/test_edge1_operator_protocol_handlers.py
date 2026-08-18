#!/usr/bin/env python3
"""Protocol boundary smoke tests for Edge1 Operator."""

from server.edge1_operator_protocol import Edge1OperatorProtocol


class RecordingDispatcher:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        return self.result


def test_protocol_delegates_request_to_dispatcher():
    dispatcher = RecordingDispatcher({"ok": True})
    protocol = Edge1OperatorProtocol(dispatcher)
    request = {"method": "tools/list", "payload": {}}

    assert protocol.handle(request) == {"ok": True}
    assert dispatcher.requests == [request]


def test_protocol_returns_dispatcher_rejection():
    dispatcher = RecordingDispatcher({"ok": False, "error": "unknown_tool"})
    protocol = Edge1OperatorProtocol(dispatcher)
    request = {"method": "tools/call", "payload": {"name": "missing"}}

    assert protocol.handle(request) == {"ok": False, "error": "unknown_tool"}
    assert dispatcher.requests == [request]
