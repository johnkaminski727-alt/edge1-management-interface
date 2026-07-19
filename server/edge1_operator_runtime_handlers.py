"""Runtime handlers exposed through the Edge1 Operator dispatch layer.

Handlers intentionally keep execution boundaries narrow. They are designed to
be invoked by the dispatcher after validation and audit preparation.
"""

from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class HandlerResult:
    ok: bool
    operation: str
    details: dict

