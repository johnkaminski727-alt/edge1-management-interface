#!/usr/bin/env python3
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "server" / "telephony_analytics_api.py"
PLATFORM = ROOT / "server" / "telephony_platform.py"

for path in (API, PLATFORM):
    if not path.is_file():
        raise SystemExit(f"missing telephony platform file: {path.relative_to(ROOT)}")
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

source = API.read_text(encoding="utf-8")
for marker in (
    "127.0.0.1",
    "LOOPBACK_HOSTS",
    "/api/telephony/platform/health",
    "/api/telephony/platform/calls/summary",
    "/api/telephony/platform/interconnects/summary",
    "METHOD_NOT_ALLOWED",
    "read_only",
    "Content-Security-Policy",
    "X-Frame-Options",
    "CallEvent",
    "summarize_calls",
    "analyze_interconnects",
    "health_score",
):
    if marker not in source:
        raise SystemExit(f"analytics API missing marker: {marker}")

if "do_PUT" in source or "do_DELETE" in source or "do_PATCH" in source:
    raise SystemExit("analytics API must not expose write methods")

print("telephony analytics API validation passed")
