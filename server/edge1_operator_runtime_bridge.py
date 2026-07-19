"""Runtime bridge for Edge1 Operator.

Connects the dispatcher layer to controlled runtime handlers.
This module intentionally keeps transport concerns separate from host operations.
"""

from .edge1_operator_runtime_handlers import RuntimeHandlers


class RuntimeBridge:
    def __init__(self, handlers=None):
        self.handlers = handlers or RuntimeHandlers()

    def execute(self, operation, payload=None):
        payload = payload or {}
        handler = getattr(self.handlers, operation, None)
        if handler is None:
            raise ValueError(f"unsupported operation: {operation}")
        return handler(**payload)
