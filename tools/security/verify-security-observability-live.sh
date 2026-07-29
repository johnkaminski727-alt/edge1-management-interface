#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
STATUS_URL=${EDGE1_STATUS_URL:-http://127.0.0.1/edge1-status}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/security-observability-acceptance}
MAX_AGE_SECONDS=${SECURITY_OBSERVABILITY_MAX_AGE_SECONDS:-600}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR=${1:-$EVIDENCE_ROOT/$STAMP}
CORRELATION_JSON="$EVIDENCE_DIR/security-correlation.json"
NETWORK_DEFENSE_JSON="$EVIDENCE_DIR/network-defense.json"
RESULT_JSON="$EVIDENCE_DIR/acceptance.json"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run as root, for example: sudo bash $0"
[ -d "$ROOT/.git" ] || fail "repository not found: $ROOT"
for command in curl date git hostname install journalctl python3 readlink sha256sum systemctl; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

HOST=$(hostname -f 2>/dev/null || hostname)
case "$HOST" in
    edge1|edge1.ww.cx) ;;
    *) fail "verification is restricted to Edge1; observed host: $HOST" ;;
esac

install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
printf '%s\n' "$HOST" > "$EVIDENCE_DIR/host.txt"
printf '%s\n' "$(id -un)" > "$EVIDENCE_DIR/principal.txt"
git -C "$ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$ROOT" status --short --branch > "$EVIDENCE_DIR/git-status.txt"

capture_failure() {
    local code=$?
    trap - ERR INT TERM
    set +e
    systemctl status \
        wwcx-security-correlation.service \
        wwcx-security-correlation.timer \
        wwcx-network-defense.service \
        wwcx-network-defense.timer \
        --no-pager > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true
    journalctl -u wwcx-security-correlation.service -n 50 --no-pager > "$EVIDENCE_DIR/failure-correlation-journal.txt" 2>&1 || true
    journalctl -u wwcx-network-defense.service -n 50 --no-pager > "$EVIDENCE_DIR/failure-network-defense-journal.txt" 2>&1 || true
    printf 'completed_at=%s\naccepted=false\nexit_code=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$code" > "$EVIDENCE_DIR/result.txt"
    printf 'Security observability acceptance failed.\n' >&2
    printf 'Failure evidence: %s\n' "$EVIDENCE_DIR" >&2
    exit "$code"
}
trap capture_failure ERR INT TERM

for timer in wwcx-security-correlation.timer wwcx-network-defense.timer; do
    [ "$(systemctl is-enabled "$timer")" = enabled ]
    [ "$(systemctl is-active "$timer")" = active ]
done

for service in wwcx-security-correlation.service wwcx-network-defense.service; do
    [ "$(systemctl show "$service" --property=Result --value)" = success ]
    [ "$(systemctl show "$service" --property=ExecMainStatus --value)" = 0 ]
done

readlink /var/www/edge1-status/security-correlation.json > "$EVIDENCE_DIR/correlation-link-target.txt"
[ "$(cat "$EVIDENCE_DIR/correlation-link-target.txt")" = "security/correlation/data/security-correlation.json" ]

curl -fsS --max-time 10 "$STATUS_URL/security-correlation.json" > "$CORRELATION_JSON"
curl -fsS --max-time 10 "$STATUS_URL/network-defense/data/network-defense.json" > "$NETWORK_DEFENSE_JSON"
curl -fsS --max-time 10 "$STATUS_URL/security/correlation.html" > "$EVIDENCE_DIR/correlation.html"
curl -fsS --max-time 10 "$STATUS_URL/network-defense/" > "$EVIDENCE_DIR/network-defense.html"

python3 "$ROOT/tools/security/verify_security_observability.py" \
    --correlation "$CORRELATION_JSON" \
    --network-defense "$NETWORK_DEFENSE_JSON" \
    --max-age-seconds "$MAX_AGE_SECONDS" \
    --output "$RESULT_JSON" | tee "$EVIDENCE_DIR/acceptance-summary.txt"

systemctl status \
    wwcx-security-correlation.service \
    wwcx-security-correlation.timer \
    wwcx-network-defense.service \
    wwcx-network-defense.timer \
    --no-pager > "$EVIDENCE_DIR/systemd-status.txt" || true
journalctl -u wwcx-security-correlation.service -n 50 --no-pager > "$EVIDENCE_DIR/correlation-journal.txt" || true
journalctl -u wwcx-network-defense.service -n 50 --no-pager > "$EVIDENCE_DIR/network-defense-journal.txt" || true
sha256sum "$CORRELATION_JSON" "$NETWORK_DEFENSE_JSON" "$RESULT_JSON" > "$EVIDENCE_DIR/sha256.txt"
printf 'completed_at=%s\naccepted=true\nread_only=true\ntraffic_controls_changed=false\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Security observability acceptance passed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'Security Correlation is live and consumed by Network Defense. No traffic controls were changed.\n'
