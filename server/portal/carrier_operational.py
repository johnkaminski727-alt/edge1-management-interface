#!/usr/bin/env python3

"""Carrier-scoped operational views for the Phase 13G portal integration.

The module deliberately operates on exported JSON summaries. It does not expose
Edge1 credentials, private network topology, or mutation of production routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import