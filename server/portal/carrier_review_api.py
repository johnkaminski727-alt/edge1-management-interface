#!/usr/bin/env python3

"""Internal-only API adapter for Phase 13I carrier-support review.

This module authorizes queue reads and non-executing lifecycle review events.
Carrier identities are rejected even when internal scopes are misconfigured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from carrier_review import (
    REVIEW_READ_SCOPE,
    REVIEW_WRITE_SCOPE,
    append_review_event,
    build_review_queue,
)

RE