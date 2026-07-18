#!/usr/bin/env python3
"""Validate WW.CX records-evidence JSON and SHA-256 manifests.

The validator intentionally uses only the Python standard library so it can run
on constrained hosts and in GitHub Actions without additional dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

RECORD_ID = re.compile(r"^WWCX-[A-Z0-9][A-Z0-9._-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")