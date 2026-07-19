#!/usr/bin/env python3
"""Protocol boundary for the Edge1 Operator service."""

from __future__ import annotations

from typing import Any


class Edge1OperatorProtocol:
    """Transport-neutral request handling boundary."""

    def __init__(self, dispatcher: Any):
        self.dispatcher = dispatcher

    def handle(self, request: dict) -> dict:
        return self.dispatcher.dispatch(request)
