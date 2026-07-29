#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
UNIT_ROOT=${EDGE1_SYSTEMD_ROOT:-/etc/systemd/system}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/network-defense}
STATUS_URL=${EDGE1_STATUS_URL:-http://127.0.0.1/edge1-status}
REQUIRED_COMMIT=${NETWORK_DEFENSE_REQUIRED_COMMIT:-7b0a337dc278e3abe99c429a3987619702b3cc47}
SERVICE=wwcx-network-defense.service
TIMER=wwcx-network-defense.timer
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
BACKUP_DIR="$EVIDENCE_DIR/backups"
MUTATION_STARTED=0

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run as root, for example: sudo $0"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found: $REPO_ROOT"
for command in bash git install systemctl python3 cmp sha256sum curl; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
[ "$BRANCH" = main ] || fail "deployment requires main; current branch is $BRANCH"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository has uncommitted or untracked work; preserve it before deployment"
git -C "$REPO_ROOT" merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD || fail "main does not contain required DNS Defense merge $REQUIRED_COMMIT"

for source in \
    "$REPO_ROOT/deploy/systemd/$SERVICE" \
    "$REPO_ROOT/deploy/systemd/$TIMER" \
    "$REPO_ROOT/src/web/operations-center/index.html" \
    "$REPO_ROOT/src/web/network-defense/index.html" \
    "$REPO_ROOT/src/web/security/correlation.html" \
    "$REPO_ROOT/server/network_defense_dns_exporter.py" \
    "$REPO_ROOT/tools/networking/validate-network-defense.sh"; do
    [ -f "$source" ] || fail "required source is missing: $source"
done

mkdir -p "$BACKUP_DIR"
printf '%s\n' "$STAMP" > "$EVIDENCE_DIR/started-at.txt"
git -C "$REPO_ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$REPO_ROOT" status --short --branch > "$EVIDENCE_DIR/git-status-before.txt"

backup_path() {
    local path=$1
    local label=$2
    if [ -e "$path" ]; then
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
    if [ "$state" = present ]; then
        install -d -m 0755 "$(dirname "$path")"
        rm -rf "$path"
        cp -a "$BACKUP_DIR/$label" "$path"
    else
        rm -rf "$path"
    fi
}

TIMER_ENABLED_BEFORE=$(systemctl is-enabled "$TIMER" 2>/dev/null || true)
TIMER_ACTIVE_BEFORE=$(systemctl is-active "$TIMER" 2>/dev/null || true)
printf '%s\n' "$TIMER_ENABLED_BEFORE" > "$EVIDENCE_DIR/timer-enabled-before.txt"
printf '%s\n' "$TIMER_ACTIVE_BEFORE" > "$EVIDENCE_DIR/timer-active-before.txt"

backup_path "$UNIT_ROOT/$SERVICE" service.unit
backup_path "$UNIT_ROOT/$TIMER" timer.unit
backup_path "$STATUS_ROOT/index.html" operations-center.html
backup_path "$STATUS_ROOT/network-defense/index.html" network-defense.html
backup_path "$STATUS_ROOT/security/correlation.html" security-correlation.html
backup_path "$STATUS_ROOT/network-defense.json" network-defense.json

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
        restore_path "$STATUS_ROOT/index.html" operations-center.html
        restore_path "$STATUS_ROOT/network-defense/index.html" network-defense.html
        restore_path "$STATUS_ROOT/security/correlation.html" security-correlation.html
        restore_path "$STATUS_ROOT/network-defense.json" network-defense.json
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

bash "$REPO_ROOT/tools/networking/validate-network-defense.sh" | tee "$EVIDENCE_DIR/repository-validation.txt"

MUTATION_STARTED=1
install -d -m 0755 "$STATUS_ROOT/network-defense" "$STATUS_ROOT/security"
install -m 0644 "$REPO_ROOT/src/web/operations-center/index.html" "$STATUS_ROOT/index.html"
install -m 0644 "$REPO_ROOT/src/web/network-defense/index.html" "$STATUS_ROOT/network-defense/index.html"
install -m 0644 "$REPO_ROOT/src/web/security/correlation.html" "$STATUS_ROOT/security/correlation.html"
install -m 0644 "$REPO_ROOT/deploy/systemd/$SERVICE" "$UNIT_ROOT/$SERVICE"
install -m 0644 "$REPO_ROOT/deploy/systemd/$TIMER" "$UNIT_ROOT/$TIMER"

systemctl daemon-reload
systemctl enable --now "$TIMER"
systemctl start "$SERVICE"

[ "$(systemctl is-enabled "$TIMER")" = enabled ]
[ "$(systemctl is-active "$TIMER")" = active ]
[ "$(systemctl show "$SERVICE" --property=Result --value)" = success ]
[ "$(systemctl show "$SERVICE" --property=ExecMainStatus --value)" = 0 ]

cmp -s "$REPO_ROOT/src/web/operations-center/index.html" "$STATUS_ROOT/index.html"
cmp -s "$REPO_ROOT/src/web/network-defense/index.html" "$STATUS_ROOT/network-defense/index.html"
cmp -s "$REPO_ROOT/src/web/security/correlation.html" "$STATUS_ROOT/security/correlation.html"

python3 - "$STATUS_ROOT/network-defense.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
document = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(document, dict):
    raise SystemExit("network-defense snapshot is not an object")
if document.get("traffic_controls_changed") is not False:
    raise SystemExit("traffic_controls_changed must remain false")
dns = document.get("dns_policy")
if not isinstance(dns, dict):
    raise SystemExit("dns_policy readiness contract is missing")
required_false = ("enforcement_enabled", "enforcement_verified", "traffic_controls_changed")
for key in required_false:
    if dns.get(key) is not False:
        raise SystemExit(f"dns_policy.{key} must remain false")
if dns.get("requires_explicit_activation") is not True:
    raise SystemExit("dns_policy.requires_explicit_activation must be true")
print(json.dumps({
    "ok": True,
    "overall_state": document.get("overall_state"),
    "dns_policy_state": (document.get("components") or {}).get("dns_policy", {}).get("state"),
    "enforcement_enabled": False,
    "traffic_controls_changed": False,
}))
PY

curl -fsS --max-time 10 "$STATUS_URL/" > "$EVIDENCE_DIR/operations-center.html"
curl -fsS --max-time 10 "$STATUS_URL/network-defense/" > "$EVIDENCE_DIR/network-defense.html"
curl -fsS --max-time 10 "$STATUS_URL/security/correlation.html" > "$EVIDENCE_DIR/security-correlation.html"
curl -fsS --max-time 10 "$STATUS_URL/network-defense.json" > "$EVIDENCE_DIR/network-defense.json"

systemctl status "$SERVICE" "$TIMER" --no-pager > "$EVIDENCE_DIR/systemd-status.txt" || true
journalctl -u "$SERVICE" -n 50 --no-pager > "$EVIDENCE_DIR/service-journal.txt" || true
sha256sum \
    "$UNIT_ROOT/$SERVICE" \
    "$UNIT_ROOT/$TIMER" \
    "$STATUS_ROOT/index.html" \
    "$STATUS_ROOT/network-defense/index.html" \
    "$STATUS_ROOT/security/correlation.html" \
    "$STATUS_ROOT/network-defense.json" > "$EVIDENCE_DIR/sha256.txt"
printf 'completed_at=%s\nrolled_back=false\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Network Defense observability deployment passed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'DNS enforcement remains disabled; no resolver configuration was installed or reloaded.\n'
