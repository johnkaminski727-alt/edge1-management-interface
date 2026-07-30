#!/usr/bin/env python3
"""Redact common secret-bearing assignments from streamed Edge1 evidence text."""
from __future__ import annotations

import re
import sys

ASSIGNMENT = re.compile(
    r"(?i)(password|passwd|secret|token|cookie|authorization|client_secret|private_key|passphrase)(\s*[:=]\s*)(\S+)"
)
URL_CREDENTIAL = re.compile(r"(?i)(https?://)([^/@\s:]+):([^/@\s]+)@")
BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")


def redact(line: str) -> str:
    line = URL_CREDENTIAL.sub(r"\1<redacted>@", line)
    line = ASSIGNMENT.sub(r"\1\2<redacted>", line)
    line = BEARER.sub(r"\1 <redacted>", line)
    return line


def main() -> int:
    for line in sys.stdin:
        sys.stdout.write(redact(line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
