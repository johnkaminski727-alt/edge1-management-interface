#!/usr/bin/env python3
"""Edge1 Operator runtime primitives.

Provides bounded execution helpers used by the MCP service.
The runtime intentionally keeps credentials and privileged configuration
outside the repository.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

EVIDENCE_ROOT = Path(os.environ.get("EDGE1_OPERATOR_EVIDENCE", "/var/lib/edge1-operator/evidence"))


def execution_id() -> str:
    return uuid.uuid4().hex[:16