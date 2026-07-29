#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
DATA_ROOT=${EDGE1_SECURITY_CORRELATION_DATA_ROOT:-$STATUS_ROOT/security/correlation/data}
DATA_FILE="$DATA_ROOT/security-correlation.json"
LEGACY_LINK="$STATUS_ROOT/security-correlation.json"
UNIT_ROOT=${EDGE1_SYSTEMD_ROOT:-/etc/systemd/system}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/security-correlation}
STATUS_URL=${EDGE1_STATUS_URL:-http://127.0.0.1/edge1-status}
REQUIRED_COMMIT=${SECURITY_CORRELATION_REQUIRED_COMMIT:-5b12904ab8b1e6182df167715d7022092a6d27d8}
SERVICE=wwcx-security-correlation.service
TIMER=wwcx-security-correlation.timer
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
BACKUP_DIR="$EVIDENCE_DIR/backups"
MUTATION_STARTED=0

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run as root, for example: sudo bash $0"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found: $REPO_ROOT"
for command in bash git install systemctl python3 cmp sha256sum curl ln readlink journalctl; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
[ "$BRANCH" = main ] || fail "deployment requires main; current branch is $BRANCH"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository has uncommitted or untracked work; preserve it before deployment"
git -C "$REPO_ROOT" merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD || fail "main does not contain required Security Correlation merge $REQUIRED_COMMIT"

for source in \
    "$REPO_ROOT/deploy/systemd/$SERVICE" \
    "$REPO_ROOT/deploy/systemd/$TIMER" \
    "$REPO_ROOT/src/web/security/correlation.html" \
    "$REPO_ROOT/server/security_correlation_exporter.py" \
    "$REPO_ROOT/tools/security/validate-security-correlation.sh"; do
    [ -f "$source" ] || fail "required source is missing: $source"
done

mkdir -p "$BACKUP_DIR"
printf '%s\n' "$STAMP" > "$EVIDENCE_DIR/started-at.txt"
git -C "$REPO_ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$REPO_ROOT" status --short --branch > "$EVIDENCE_DIR/git-status-before.txt"
printf '%s\n' "$DATA_FILE" > "$EVIDENCE_DIR/data-path.txt"
printf '%s\n' "$LEGACY_LINK" > "$EVIDENCE_DIR/compatibility-link.txt"

backup_path() {
    local path=$1
    local label=$2
    if [ -e "$path" ] || [ -L "$path" ]; then
        cp -a "$path" "$BACKUP_DIR/$label"
        printf 'present\n' > "$BACKUP_DIR/$label.state"
    else
        printf 'absent\n' > "$BACKUP_DIR/$label.state"
    fi
}

restore_path() {
    local path=$1
    local label=$2
    local state
    state=$(cat "$BACKUP_DIR/$label.state" 2>/dev/null || printf 'absent')
    rm -rf "$path"
    if [ "$state" = present ]; then
        install -d -m 0755 "$(dirname "$path")"
        cp -a "$BACKUP_DIR/$label" "$path"
    fi
}

TIMER_ENABLED_BEFORE=$(systemctl is-enabled "$TIMER" 2>/dev/null || true)
TIMER_ACTIVE_BEFORE=$(systemctl is-active "$TIMER" 2>/dev/null || true)
printf '%s\n' "$TIMER_ENABLED_BEFORE" > "$EVIDENCE_DIR/timer-enabled-before.txt"
printf '%s\n' "$TIMER_ACTIVE_BEFORE" > "$EVIDENCE_DIR/timer-active-before.txt"

backup_path "$UNIT_ROOT/$SERVICE" service.unit
backup_path "$UNIT_ROOT/$TIMER" timer.unit
backup_path "$STATUS_ROOT/security/correlation.html" correlation.html
backup_path "$DATA_ROOT" correlation-data
backup_path "$LEGACY_LINK" legacy-correlation.json

rollback() {
    local code=$?
    trap - ERR INT TERM
    set +e
    if [ "$MUTATION_STARTED" -eq 1 ]; then
        printf 'Deployment failed; capturing diagnostics and restoring saved files.\n' >&2
        systemctl status "$SERVICE" "$TIMER" --no-pager > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true
        journalctl -u "$SERVICE" -n 100 --no-pager > "$EVIDENCE_DIR/failure-service-journal.txt" 2>&1 || true
        systemctl stop "$TIMER" >/dev/null 2>&1 || true
        restore_path "$UNIT_ROOT/$SERVICE" service.unit
        restore_path "$UNIT_ROOT/$TIMER" timer.unit
        restore_path "$STATUS_ROOT/security/correlation.html" correlation.html
        restore_path "$DATA_ROOT" correlation-data
        restore_path "$LEGACY_LINK" legacy-correlation.json
        systemctl daemon-reload >/dev/null 2>&1 || true
        case "$TIMER_ENABLED_BEFORE" in
            enabled|enabled-runtime) systemctl enable "$TIMER" >/dev/null 2>&1 || true ;;
            *) systemctl disable "$TIMER" >/dev/null 2>&1 || true ;;
        esac
        if [ "$TIMER_ACTIVE_BEFORE" = active ]; then
            systemctl start "$TIMER" >/dev/null 2>&1 || true
        fi
        printf 'rolled_back=true\nexit_code=%s\n' "$code" > "$EVIDENCE_DIR/rollback.txt"
        printf 'Failure evidence: %s\n' "$EVIDENCE_DIR" >&2
    fi
    exit "$code"
}
trap rollback ERR INT TERM

bash "$REPO_ROOT/tools/security/validate-security-correlation.sh" | tee "$EVIDENCE_DIR/repository-validation.txt"

MUTATION_STARTED=1
install -d -m 0755 "$STATUS_ROOT/security"
install -d -o root -g root -m 0755 "$DATA_ROOT"
install -m 0644 "$REPO_ROOT/src/web/security/correlation.html" "$STATUS_ROOT/security/correlation.html"
install -m 0644 "$REPO_ROOT/deploy/systemd/$SERVICE" "$UNIT_ROOT/$SERVICE"
install -m 0644 "$REPO_ROOT/deploy/systemd/$TIMER" "$UNIT_ROOT/$TIMER"
ln -sfn "security/correlation/data/security-correlation.json" "$LEGACY_LINK"

systemctl daemon-reload
systemctl enable --now "$TIMER"
systemctl start "$SERVICE"

[ "$(systemctl is-enabled "$TIMER")" = enabled ]
[ "$(systemctl is-active "$TIMER")" = active ]
[ "$(systemctl show "$SERVICE" --property=Result --value)" = success ]
[ "$(systemctl show "$SERVICE" --property=ExecMainStatus --value)" = 0 ]
[ -f "$DATA_FILE" ]
[ -L "$LEGACY_LINK" ]
[ "$(readlink "$LEGACY_LINK")" = "security/correlation/data/security-correlation.json" ]
cmp -s "$DATA_FILE" "$LEGACY_LINK"
cmp -s "$REPO_ROOT/src/web/security/correlation.html" "$STATUS_ROOT/security/correlation.html"

python3 - "$DATA_FILE" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
document = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(document, dict):
    raise SystemExit("security-correlation snapshot is not an object")
if document.get("read_only") is not True:
    raise SystemExit("read_only must be true")
privacy = document.get("privacy")
if not isinstance(privacy, dict):
    raise SystemExit("privacy contract is missing")
for key in ("packet_payloads_included", "credentials_included", "private_keys_included", "raw_logs_included"):
    if privacy.get(key) is not False:
        raise SystemExit(f"privacy.{key} must be false")
if privacy.get("event_fields_minimized") is not True:
    raise SystemExit("privacy.event_fields_minimized must be true")
summary = document.get("summary")
if not isinstance(summary, dict):
    raise SystemExit("summary contract is missing")
print(json.dumps({
    "ok": True,
    "read_only": True,
    "events": summary.get("event_count"),
    "correlations": summary.get("correlation_count"),
    "available_sources": summary.get("available_source_count"),
}))
PY

curl -fsS --max-time 10 "$STATUS_URL/security/correlation.html" > "$EVIDENCE_DIR/correlation.html"
curl -fsS --max-time 10 "$STATUS_URL/security-correlation.json" > "$EVIDENCE_DIR/security-correlation.json"

systemctl status "$SERVICE" "$TIMER" --no-pager > "$EVIDENCE_DIR/systemd-status.txt" || true
journalctl -u "$SERVICE" -n 50 --no-pager > "$EVIDENCE_DIR/service-journal.txt" || true
readlink "$LEGACY_LINK" > "$EVIDENCE_DIR/compatibility-link-target.txt"
sha256sum \
    "$UNIT_ROOT/$SERVICE" \
    "$UNIT_ROOT/$TIMER" \
    "$STATUS_ROOT/security/correlation.html" \
    "$DATA_FILE" > "$EVIDENCE_DIR/sha256.txt"
printf 'completed_at=%s\nrolled_back=false\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Security Correlation observability deployment passed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'No IDS, DNS, firewall, proxy, routing, Fail2ban, or reputation-filter controls were changed.\n'
