#!/usr/bin/env python3
"""Edge1 Operator MCP protocol boundary.

This module provides the transport-neutral protocol boundary used by the
Edge1 Operator service. Network transport and authentication are intentionally
kept outside this module so the service can run behind an approved private
connector.
"""

from __future__ import annotations

import json
from typing import Any, Dict


TOOLS = [
    {
        "name": "edge1.identity",
        "description": "Return verified Edge1 operator identity information.",
        "inputSchema": {"type": "object