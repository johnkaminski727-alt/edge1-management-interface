#!/usr/bin/env bash
set -Eeuo pipefail

MANIFEST="${1:-config/production-node/node-manifest.example.json}"
EVIDENCE_DIR="${EVIDENCE_DIR:-./artifacts/production-node-preflight}"
mkdir -p "$EVIDENCE_DIR"

python3 deploy/production-node/validate-manifest.py "$MANIFEST" | tee "$EVIDENCE_DIR/manifest-validation.txt"

{
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname -f 2>/dev/null || hostname)"
  echo "kernel=$(uname -srmo)"
  echo "uid=$(id -u)"
  echo "user=$(id -un)"
  echo "root_free_mb=$(df -Pm / | awk 'NR==2 {print $4}')"
  echo "memory_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
} | tee "$EVIDENCE_DIR/host-facts.txt"

python3 - "$MANIFEST" <<'PY' | tee "$EVIDENCE_DIR/required-commands.txt"
import json, shutil, sys
manifest=json.load(open(sys.argv[1], encoding="utf-8"))
missing=[]
for command in manifest["host"]["required_commands"]:
    path=shutil.which(command)
    print("%s=%s" % (command, path or "MISSING"))
    if not path:
        missing.append(command)
if missing:
    raise SystemExit("missing required commands: %s" % ", ".join(missing))
PY

ss -lntup 2>/dev/null | tee "$EVIDENCE_DIR/listeners.txt" || ss -lnt 2>/dev/null | tee "$EVIDENCE_DIR/listeners.txt"
systemctl --failed --no-legend 2>/dev/null | tee "$EVIDENCE_DIR/failed-units.txt" || true

echo "production node host preflight passed"
