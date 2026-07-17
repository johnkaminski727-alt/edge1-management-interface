#!/usr/bin/env bash
set -euo pipefail

src="${BB_LIBRARY_DB:-/var/lib/bigbird-ai-library/library.sqlite3}"
backup_dir="${BB_LIBRARY_BACKUP_DIR:-/var/backups/bigbird-ai-library}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
base="bigbird-ai-library-${timestamp}.sqlite3"
tmp_path="${backup_dir}/${base}"
gz_path="${tmp_path}.gz"
manifest_path="${gz_path}.sha256"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo so the backup can read the private library database." >&2
  exit 1
fi

if [[ ! -f "$src" ]]; then
  echo "Library database not found: $src" >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$backup_dir"

SRC="$src" DST="$tmp_path" python3 - <<'PY'
import os
import sqlite3
from pathlib import Path

src = Path(os.environ["SRC"])
dst = Path(os.environ["DST"])

dst.parent.mkdir(parents=True, exist_ok=True)
if dst.exists():
    dst.unlink()

source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
try:
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
    finally:
        target.close()
finally:
    source.close()
PY

chmod 0600 "$tmp_path"
gzip -9 "$tmp_path"
chmod 0600 "$gz_path"
sha256sum "$gz_path" > "$manifest_path"
chmod 0600 "$manifest_path"

echo "backup: $gz_path"
echo "manifest: $manifest_path"
cat "$manifest_path"

