#!/usr/bin/env python3

import shutil
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

STAMP = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

TARGET = ROOT / "data" / "registry" / "snapshots" / STAMP

TARGET.mkdir(parents=True, exist_ok=True)

for src in [
    ROOT / "data/registry/countries.json",
    ROOT / "data/registry/calling_codes.json",
    ROOT / "data/registry/timezones.json",
    ROOT / "data/telecom/numbering.db",
]:
    shutil.copy2(src, TARGET / src.name)

print(f"Registry snapshot created: {TARGET}")
