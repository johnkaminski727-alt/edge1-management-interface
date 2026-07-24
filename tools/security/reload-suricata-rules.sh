#!/usr/bin/env bash
set -Eeuo pipefail

EVIDENCE_DIR="/var/lib/edge1-operations-api/evidence/security"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$EVIDENCE_DIR/reload-$STAMP.json"

mkdir -p "$EVIDENCE_DIR"

START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

systemctl reload suricata.service

cat > "$OUT" <<EOF
{
  "action": "security.rules.reload",
  "started": "$START",
  "completed": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "result": "success"
}
EOF

cat "$OUT"
