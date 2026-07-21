#!/usr/bin/env python3
"""Inventory navigable PHP pages without inventing routes.

The tool scans a supplied CX Admin document root, extracts conservative metadata,
and emits JSON suitable for review before building a canonical menu registry.
It does not modify the scanned tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

TITLE_PATTERNS = [
    re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S),
    re