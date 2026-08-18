#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
EXPECTED_COMMIT="${EXPECTED_COMMIT:-}"
HOST="$(hostname -f 2>/dev/null || hostname)"
LEGACY_SERVICE="suricata.service"
SENSOR_SERVICE="wwcx-network-sensor-suricata.service"
UPDATE_SERVICE="wwcx-suricata-update.service"
UPDATE_TIMER="wwcx-suricata-update.timer"
UPDATER_SOURCE="$ROOT/deploy/security/wwcx-suricata-update"
UPDATER_LIVE="/usr/local/sbin/wwcx-suricata-update"
SERVICE_SOURCE="$ROOT/deploy/systemd/wwcx-suricata-update.service"
SERVICE_LIVE="/etc/systemd/system/wwcx-suricata-update.service"
TIMER_SOURCE="$ROOT/deploy/systemd/wwcx-suricata-update.timer"
TIMER_LIVE="/etc/systemd/system/wwcx-suricata-update.timer"
RETENTION_DROPIN="/etc/systemd/system/wwcx-suricata-update.service.d/retention.conf"
RETENTION_HELPER="/usr/local/sbin/wwcx-suricata-rule-backup-prune"
EVIDENCE_ROOT="${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/suricata-update-runtime-repair}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="${1:-$EVIDENCE_ROOT/$STAMP}"
BACKUP_DIR="$EVIDENCE_DIR/backups"
MUTATION_STARTED=false

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

capture_file() {
    src=$1
    dst=$2
    if [ -e "$src" ]; then
        cp -a "$src" "$dst"
        return 0
    fi
    return 1
}

LEGACY_ENABLED="$(systemctl is-enabled "$LEGACY_SERVICE" 2>/dev/null || true)"
LEGACY_ACTIVE="$(systemctl is-active "$LEGACY_SERVICE" 2>/dev/null || true)"
TIMER_ENABLED="$(systemctl is-enabled "$UPDATE_TIMER" 2>/dev/null || true)"
TIMER_ACTIVE="$(systemctl is-active "$UPDATE_TIMER" 2>/dev/null || true)"
UPDATER_WAS_PRESENT=false
SERVICE_WAS_PRESENT=false
TIMER_WAS_PRESENT=false

restore_legacy_state() {
    case "$LEGACY_ENABLED" in
        enabled|enabled-runtime) systemctl enable "$LEGACY_SERVICE" >/dev/null 2>&1 || true ;;
        *) systemctl disable "$LEGACY_SERVICE" >/dev/null 2>&1 || true ;;
    esac
    if [ "$LEGACY_ACTIVE" = active ]; then
        systemctl start "$LEGACY_SERVICE" >/dev/null 2>&1 || true
    else
        systemctl stop "$LEGACY_SERVICE" >/dev/null 2>&1 || true
    fi
}

restore_runtime_files() {
    if [ "$UPDATER_WAS_PRESENT" = true ]; then
        install -o root -g root -m 0750 "$BACKUP_DIR/wwcx-suricata-update" "$UPDATER_LIVE"
    else
        rm -f "$UPDATER_LIVE"
    fi
    if [ "$SERVICE_WAS_PRESENT" = true ]; then
        cp -a "$BACKUP_DIR/wwcx-suricata-update.service" "$SERVICE_LIVE"
    else
        rm -f "$SERVICE_LIVE"
    fi
    if [ "$TIMER_WAS_PRESENT" = true ]; then
        cp -a "$BACKUP_DIR/wwcx-suricata-update.timer" "$TIMER_LIVE"
    else
        rm -f "$TIMER_LIVE"
    fi
    systemctl daemon-reload >/dev/null 2>&1 || true
}

rollback() {
    code=$?
    trap - ERR INT TERM
    set +e
    if [ "$MUTATION_STARTED" = true ]; then
        systemctl status "$LEGACY_SERVICE" "$SENSOR_SERVICE" "$UPDATE_SERVICE" "$UPDATE_TIMER" --no-pager \
            > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true
        ps -eo user,group,pid,ppid,etimes,rss,cmd | grep '[s]uricata' \
            > "$EVIDENCE_DIR/failure-suricata-processes.txt" 2>&1 || true
        restore_runtime_files
        restore_legacy_state
        printf 'completed_at=%s\naccepted=false\nrolled_back=true\nexit_code=%s\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$code" > "$EVIDENCE_DIR/result.txt"
        printf 'Suricata updater runtime repair failed; prior files and legacy service state were restored.\n' >&2
        printf 'Failure evidence: %s\n' "$EVIDENCE_DIR" >&2
    fi
    exit "$code"
}
trap rollback ERR INT TERM

[ "$(id -u)" -eq 0 ] || fail "run as root"
case "$HOST" in
    edge1|edge1.ww.cx) ;;
    *) fail "repair is restricted to Edge1; observed host: $HOST" ;;
esac
[ -d "$ROOT/.git" ] || fail "repository not found: $ROOT"
[ -n "$EXPECTED_COMMIT" ] || fail "EXPECTED_COMMIT is required"
printf '%s\n' "$EXPECTED_COMMIT" | grep -Eq '^[0-9a-f]{40}$' || fail "EXPECTED_COMMIT must be a full lowercase commit SHA"
[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=all)" ] || fail "repository is not clean"

SOURCE_HEAD="$(git -C "$ROOT" rev-parse HEAD)"
SOURCE_BRANCH="$(git -C "$ROOT" branch --show-current)"
if [ "$SOURCE_BRANCH" = main ]; then
    git -C "$ROOT" merge-base --is-ancestor "$EXPECTED_COMMIT" HEAD || fail "required repair commit is missing from main"
elif [ -z "$SOURCE_BRANCH" ] && [ "$SOURCE_HEAD" = "$EXPECTED_COMMIT" ]; then
    : # exact detached worktree is accepted for bounded deployment
else
    fail "source must be clean main containing EXPECTED_COMMIT or an exact detached EXPECTED_COMMIT worktree"
fi

for path in "$UPDATER_SOURCE" "$SERVICE_SOURCE" "$TIMER_SOURCE"; do
    [ -f "$path" ] || fail "required source is missing: $path"
done
for command in bash cmp cp date free git grep hostname install pgrep ps sha256sum systemctl tr; do
    command -v "$command" >/dev/null 2>&1 || fail "required command unavailable: $command"
done

bash -n "$UPDATER_SOURCE"
grep -Fq 'SURICATA_SERVICE="${WWCX_SURICATA_SERVICE:-wwcx-network-sensor-suricata.service}"' "$UPDATER_SOURCE" || fail "updater lacks managed service default"
if grep -Fq 'suricatasc -c reload-rules' "$UPDATER_SOURCE"; then
    fail "updater still contains legacy suricatasc reload"
fi
grep -Fq 'systemctl reload "$SURICATA_SERVICE"' "$UPDATER_SOURCE" || fail "updater lacks managed systemd reload"
grep -Fq 'Requires=wwcx-network-sensor-suricata.service' "$SERVICE_SOURCE" || fail "update service lacks managed sensor dependency"
if grep -Fq 'Requires=suricata.service' "$SERVICE_SOURCE"; then
    fail "update service still requires legacy Suricata"
fi
grep -Fq 'Unit=wwcx-suricata-update.service' "$TIMER_SOURCE" || fail "timer target is unexpected"

systemctl is-active --quiet "$SENSOR_SERVICE" || fail "$SENSOR_SERVICE is not active"
systemctl is-enabled --quiet "$SENSOR_SERVICE" || fail "$SENSOR_SERVICE is not enabled"
[ "$TIMER_ACTIVE" = active ] || fail "$UPDATE_TIMER must already be active; repair will not trigger a dormant persistent timer"
case "$TIMER_ENABLED" in
    enabled|enabled-runtime) ;;
    *) fail "$UPDATE_TIMER must already be enabled" ;;
esac
[ -f "$RETENTION_DROPIN" ] || fail "retention drop-in is missing: $RETENTION_DROPIN"
grep -Fq "ExecStartPost=$RETENTION_HELPER" "$RETENTION_DROPIN" || fail "retention drop-in has an unexpected ExecStartPost"
[ -x "$RETENTION_HELPER" ] || fail "retention helper is missing or not executable: $RETENTION_HELPER"

install -d -o root -g root -m 0700 "$EVIDENCE_DIR" "$BACKUP_DIR"
printf '%s\n' "$HOST" > "$EVIDENCE_DIR/host.txt"
printf '%s\n' "$EXPECTED_COMMIT" > "$EVIDENCE_DIR/expected-commit.txt"
printf '%s\n' "$SOURCE_HEAD" > "$EVIDENCE_DIR/revision.txt"
git -C "$ROOT" status --short --branch > "$EVIDENCE_DIR/git-status.txt"
printf 'legacy_enabled=%s\nlegacy_active=%s\ntimer_enabled=%s\ntimer_active=%s\n' \
    "$LEGACY_ENABLED" "$LEGACY_ACTIVE" "$TIMER_ENABLED" "$TIMER_ACTIVE" \
    > "$EVIDENCE_DIR/service-state-before.txt"
systemctl status "$LEGACY_SERVICE" "$SENSOR_SERVICE" "$UPDATE_SERVICE" "$UPDATE_TIMER" --no-pager \
    > "$EVIDENCE_DIR/systemd-status-before.txt" 2>&1 || true
ps -eo user,group,pid,ppid,etimes,rss,cmd | grep '[s]uricata' \
    > "$EVIDENCE_DIR/suricata-processes-before.txt" 2>&1 || true
free -h > "$EVIDENCE_DIR/memory-before.txt"

if capture_file "$UPDATER_LIVE" "$BACKUP_DIR/wwcx-suricata-update"; then UPDATER_WAS_PRESENT=true; fi
if capture_file "$SERVICE_LIVE" "$BACKUP_DIR/wwcx-suricata-update.service"; then SERVICE_WAS_PRESENT=true; fi
if capture_file "$TIMER_LIVE" "$BACKUP_DIR/wwcx-suricata-update.timer"; then TIMER_WAS_PRESENT=true; fi
sha256sum "$UPDATER_SOURCE" "$SERVICE_SOURCE" "$TIMER_SOURCE" > "$EVIDENCE_DIR/source.sha256"

MUTATION_STARTED=true
install -o root -g root -m 0750 "$UPDATER_SOURCE" "$UPDATER_LIVE"
install -o root -g root -m 0644 "$SERVICE_SOURCE" "$SERVICE_LIVE"
install -o root -g root -m 0644 "$TIMER_SOURCE" "$TIMER_LIVE"
cmp -s "$UPDATER_SOURCE" "$UPDATER_LIVE"
cmp -s "$SERVICE_SOURCE" "$SERVICE_LIVE"
cmp -s "$TIMER_SOURCE" "$TIMER_LIVE"

systemctl daemon-reload
systemctl is-active --quiet "$UPDATE_TIMER"
systemctl is-enabled --quiet "$UPDATE_TIMER"

# Retire the duplicate legacy runtime only after the replacement updater contract is loaded.
systemctl disable --now "$LEGACY_SERVICE"

systemctl is-active --quiet "$SENSOR_SERVICE"
[ "$(systemctl is-active "$LEGACY_SERVICE" 2>/dev/null || true)" = inactive ]
case "$(systemctl is-enabled "$LEGACY_SERVICE" 2>/dev/null || true)" in
    disabled|not-found) ;;
    *) fail "$LEGACY_SERVICE remains enabled" ;;
esac
systemctl is-active --quiet "$UPDATE_TIMER"
systemctl is-enabled --quiet "$UPDATE_TIMER"

REQUIRES="$(systemctl show "$UPDATE_SERVICE" --property=Requires --value)"
printf '%s\n' "$REQUIRES" | grep -Fq "$SENSOR_SERVICE" || fail "loaded update unit does not require managed sensor"
if printf '%s\n' "$REQUIRES" | grep -Fq "$LEGACY_SERVICE"; then
    fail "loaded update unit still requires legacy Suricata"
fi

systemctl cat "$UPDATE_SERVICE" > "$EVIDENCE_DIR/update-service-after.txt"
[ "$(grep -Fc "ExecStartPost=$RETENTION_HELPER" "$EVIDENCE_DIR/update-service-after.txt")" -eq 1 ] || fail "retention ExecStartPost is missing or duplicated"

SENSOR_PIDS="$(pgrep -u suricata -f '^/usr/bin/suricata ' || true)"
SENSOR_PID_COUNT="$(printf '%s\n' "$SENSOR_PIDS" | awk 'NF {count += 1} END {print count + 0}')"
[ "$SENSOR_PID_COUNT" -eq 1 ] || fail "expected exactly one Suricata runtime process; observed $SENSOR_PID_COUNT"
set -- $SENSOR_PIDS
tr '\0' ' ' < "/proc/$1/cmdline" > "$EVIDENCE_DIR/suricata-command-after.txt"
grep -Fq -- '--pcap=' "$EVIDENCE_DIR/suricata-command-after.txt" || fail "remaining Suricata process is not the managed libpcap sensor"

systemctl cat "$UPDATE_TIMER" > "$EVIDENCE_DIR/update-timer-after.txt"
systemctl status "$LEGACY_SERVICE" "$SENSOR_SERVICE" "$UPDATE_SERVICE" "$UPDATE_TIMER" --no-pager \
    > "$EVIDENCE_DIR/systemd-status-after.txt" 2>&1 || true
ps -eo user,group,pid,ppid,etimes,rss,cmd | grep '[s]uricata' \
    > "$EVIDENCE_DIR/suricata-processes-after.txt" 2>&1 || true
free -h > "$EVIDENCE_DIR/memory-after.txt"
sha256sum "$UPDATER_LIVE" "$SERVICE_LIVE" "$TIMER_LIVE" > "$EVIDENCE_DIR/live.sha256"

systemctl reset-failed "$UPDATE_SERVICE" || true

printf 'completed_at=%s\naccepted=true\nrolled_back=false\nlegacy_service_disabled=true\nmanaged_sensor_active=true\nupdate_timer_state_preserved=true\nretention_dropin_preserved=true\nupdater_targets_managed_sensor=true\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Edge1 Suricata updater runtime repair passed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
