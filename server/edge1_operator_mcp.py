#!/usr/bin/env python3
"""Authenticated, auditable Edge1 operator MCP service.

The service binds to localhost by default and is intended to be reached through
an approved private tunnel. Credentials remain server-side. Every tool returns
structured evidence metadata and mutations are bounded by explicit policy.
"""

from __future__ import annotations

import hashlib
import json
import os
