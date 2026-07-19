#!/usr/bin/env python3
"""Edge1 Operator runtime primitives."""

from __future__ import annotations

import os
import uuid
from pathlib import Path


EVIDENCE_ROOT = Path(
    os.environ.get(
        "EDGE1_OPERATOR_EVIDENCE",
        "/var/lib/edge1-operator/evidence",
    )
)


def execution_id() -> str:
    return uuid.uuid4().hex[:16]


class Edge1OperatorRuntime:
    """Bounded runtime interface."""

    def identity(self) -> dict:
        return {
            "service": "edge1-operator",
            "status": "ready",
        }

    def health(self) -> dict:
        return {
            "status": "ok",
        }
