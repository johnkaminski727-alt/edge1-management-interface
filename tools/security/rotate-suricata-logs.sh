#!/usr/bin/env bash
set -Eeuo pipefail

EVIDENCE_DIR="/var/lib/edge1-operations-api/evidence/security"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$EVIDENCE_DIR/logrotate-$STAMP.json"

mkdir -p "$EVIDENCE_DIR"

START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

logrotate -f /etc/logrotate.d/suricata

cat > "$OUT" <<EOF
{
  "action": "security.logs.rotate",
  "started": "$START",
  "completed": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "result": "success"
}
EOF

cat "$OUT"
