#!/usr/bin/env python3
"""Serve the Big Bird telephony console and a bounded read-only status API."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from telephony