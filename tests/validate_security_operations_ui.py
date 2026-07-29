#!/usr/bin/env python3
from pathlib import Path

PAGE = Path(__file__).parents[1] / "src" / "web" / "security" / "index.html"
text = PAGE.read_text(encoding="utf-8")

required = (
    'class="alert-toggle"',
    'data-alert-id=',
    'aria-expanded=',
    'aria-controls=',
    'const openAlerts=new Set()',
    'cache:"no-store"',
    'last_known_good',
    'Only approved fields from the sanitized snapshot are displayed.',
    'Packet payloads and raw logs are not shown.',
)

missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit(f"Security Operations UI markers missing: {missing}")

forbidden = (
    "localStorage.setItem",
    "sessionStorage.setItem",
    "JSON.stringify(alert)",
    "packet.payload",
)

present = [marker for marker in forbidden if marker in text]
if present:
    raise SystemExit(f"Security Operations UI contains forbidden cache/raw-data markers: {present}")

print("Security Operations UI validation passed")
