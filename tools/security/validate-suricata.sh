#!/usr/bin/env bash
set -Eeuo pipefail

EVIDENCE_DIR="/var/lib/edge1-operations-api/evidence/security"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$EVIDENCE_DIR/validate-$STAMP.json"

mkdir -p "$EVIDENCE_DIR"

START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if suricata -T -c /etc/suricata/suricata.yaml >/tmp/suricata-validation.out 2>&1; then
    RESULT="success"
else
    RESULT="failed"
fi

cat > "$OUT" <<EOF
{
  "action": "security.validate_config",
  "started": "$START",
  "completed": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "result": "$RESULT",
  "output": $(python3 -c 'import json; print(json.dumps(open("/tmp/suricata-validation.out").read()))')
}
EOF

cat "$OUT"

test "$RESULT" = "success"
