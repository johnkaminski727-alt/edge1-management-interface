#!/usr/bin/env bash
set -Eeuo pipefail

EVIDENCE_DIR="/var/lib/edge1-operations-api/evidence/security"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$EVIDENCE_DIR/reload-$STAMP.json"
SURICATA_SERVICE="${WWCX_SURICATA_SERVICE:-wwcx-network-sensor-suricata.service}"

mkdir -p "$EVIDENCE_DIR"

START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

systemctl is-active --quiet "$SURICATA_SERVICE"
systemctl reload "$SURICATA_SERVICE"

cat > "$OUT" <<EOF
{
  "action": "security.rules.reload",
  "service": "$SURICATA_SERVICE",
  "started": "$START",
  "completed": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "result": "success"
}
EOF

cat "$OUT"
