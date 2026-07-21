#!/usr/bin/env python3
"""Local read-only API wrapper for the Edge1 Electrum watch-only wallet."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEFAULT_RPC_ENV = Path("/etc