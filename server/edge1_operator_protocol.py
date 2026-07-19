#!/usr/bin/env python3
"""Protocol boundary for the Edge1 Operator service.

This module keeps transport concerns separate from execution logic.  The
production MCP transport can call these handlers while the runtime remains
independently testable.
"""
from __future__ import annotations

from typing import Any, Callable, Dict


class Edge1OperatorProtocol:
    """Minimal tool