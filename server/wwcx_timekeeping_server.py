#!/usr/bin/env python3
"""Local JSON service exposing bounded WW.CX timekeeping actions."""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "api"))

import wwcx_timekeeping_client as client  # noqa: E402

MAX_BODY = 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "Edge1WWCXTimekeeping/1.0"

    def _send(self, status, payload):
        raw = json.dumps(payload,