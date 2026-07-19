#!/usr/bin/env python3
"""Audit helpers for Edge1 Operator runtime.

Keeps evidence records structured without storing secrets.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def write_event(root: str, event: dict) -> Path:
    directory = Path(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "audit.jsonl"
    record = dict(event)
    record.setdefault("timestamp", time.time())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def sanitize(value: str, limit: int = 10000) -> str:
    return value[:limit].replace("Authorization:", "Authorization: [redacted]")
