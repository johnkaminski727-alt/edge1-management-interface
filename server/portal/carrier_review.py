#!/usr/bin/env python3

"""Internal carrier-support review model for Phase 13I.

This module reads Phase 13H append-only intake records and appends internal
review events. It cannot approve, schedule, authorize, or execute changes.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REVIEW_READ_SCOPE = "internal.carrier.review.read"
REVIEW_WRITE_SCOPE = "internal.carrier.review.write"

RESOURCE_TYPES = frozenset({"ticket", "change_request"})
SAFE