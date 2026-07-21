"""Edge1 Operator MCP transport entrypoint.

This module defines the transport boundary for exposing the Edge1 Operator
service. The transport layer remains separate from runtime execution so
authentication, dispatch, and auditing can be validated independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TransportRequest:
    method: str
    payload: dict[str, Any]


@dataclass
class TransportResponse:
    ok: bool
    result: dict[str, Any]


class Edge1OperatorTransport:
    """Minimal transport boundary for MCP integration."""

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def handle(self, request: TransportRequest) -> TransportResponse:
        result = self.dispatcher.dispatch(
            request.method,
            **request.payload,
        )
        return TransportResponse(ok=True, result=result)
