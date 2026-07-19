"""Edge1 Operator runtime dispatch layer.

Maps registered tool names to runtime handlers while keeping protocol
handling separate from execution logic.
"""

from __future__ import annotations

from typing import Any, Callable


class OperatorDispatchError(Exception):
    """Raised when an operation cannot be dispatched."""


class OperatorDispatcher:
    def __init__(self, registry: dict[str, Callable[..., Any]] | None = None):
        self.registry = registry or {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        self.registry[name] = handler

    def dispatch(self, name: str, **kwargs: Any) -> Any:
        if name not in self.registry:
            raise OperatorDispatchError(f"unknown tool: {name}")
        return self.registry[name](**kwargs)
