#!/usr/bin/env python3
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "server" / "telephony_analytics_api.py"
PLATFORM = ROOT / "server" / "telephony_platform.py"
UNIT = ROOT / "deploy" / "telephony" / "wwcx-telephony-analytics.service"
INSTALLER = ROOT / "deploy" / "telephony" / "install-telephony-analytics.sh"
SMOKE = ROOT / "deploy" / "telephony" / "telephony-analytics-smoke-test.sh"

for path in (API, PLATFORM):
    if not path.is_file():
        raise SystemExit(f"missing telephony platform file: {path.relative_to(ROOT)}")
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

for path in (UNIT, INSTALLER, SMOKE):
    if not path.is_file():
        raise SystemExit(f"missing telephony analytics service asset: {path.relative_to(ROOT)}")

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

unit = UNIT.read_text(encoding="utf-8")
for marker in (
    "--host 127.0.0.1",
    "--port 8098",
    "NoNewPrivileges=true",
    "ProtectSystem=strict",
    "ProtectHome=true",
    "MemoryDenyWriteExecute=true",
):
    if marker not in unit:
        raise SystemExit(f"analytics systemd unit missing marker: {marker}")

installer = INSTALLER.read_text(encoding="utf-8")
for marker in (
    "systemctl enable --now wwcx-telephony-analytics.service",
    "127.0.0.1:8098/healthz",
    "unsafe public listener detected on 8098",
    "validate_telephony_platform.py",
    "validate_telephony_analytics_api.py",
):
    if marker not in installer:
        raise SystemExit(f"analytics installer missing marker: {marker}")

smoke = SMOKE.read_text(encoding="utf-8")
for marker in (
    "/api/telephony/platform/health",
    "/api/telephony/platform/calls/summary",
    "/api/telephony/platform/interconnects/summary",
    "-X POST",
    "[ \"$code\" = 405 ]",
    "unsafe public listener detected on 8098",
):
    if marker not in smoke:
        raise SystemExit(f"analytics smoke test missing marker: {marker}")

print("telephony analytics API validation passed")
