#!/bin/sh
set -eu

PREFIX=${PREFIX:-/opt/wwcx-numbering-node}
STATE_DIR=${STATE_DIR:-/var/lib/wwcx-numbering-node}
SERVICE_USER=${SERVICE_USER:-wwadmin}
PORT=${PORT:-8093}

install -d -m 0755 "$PREFIX" "$PREFIX/bin" "$PREFIX/app"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$STATE_DIR" "$STATE_DIR/raw"

cat > "$PREFIX/app/numbering_node.py" <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import