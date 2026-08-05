#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
EXPECTED_COMMIT="${EXPECTED_COMMIT:-}"
LEGACY_SERVICE="suricata.service"
SENSOR_SERVICE="wwcx-network-sensor-suricata.service"
SENSOR_UNIT_SOURCE="$ROOT/deploy/systemd/wwcx-network-sensor-suricata.service"
SENSOR_UNIT_LIVE="/etc/systemd/system/wwcx-network-sensor-suricata.service"
COLLECTOR_SOURCE="$ROOT/server/bigbird_ops_collect.py"
COLLECTOR_LIVE="/usr/local/libexec/bigbird-ops-collect.py"
PUSH_SERVICE="bigbird-ops-push.service"
SOURCE_SNAPSHOT="/var/lib/bigbird/operations-center/latest.json"
EVIDENCE_ROOT="${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/suricata-runtime-consolidation}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="${1:-$EVIDENCE_ROOT/$STAMP}"
BACKUP_DIR="$EVIDENCE_DIR/backups"
COLLECTOR_BACKUP="$BACKUP_DIR/bigbird-ops-collect.py"
SENSOR_UNIT_BACKUP="$BACKUP_DIR/wwcx-network-sensor-suricata.service"
MUTATION_STARTED=false
COLLECTOR_WAS_PRESENT=false
SENSOR_UNIT_WAS_PRESENT=false
LEGACY_ENABLED="$(systemctl is-enabled "$LEGACY_SERVICE" 2>/dev/null || true)"
LEGACY_ACTIVE="$(systemctl is-active "$LEGACY_SERVICE" 2>/dev/null || true)"
SENSOR_ENABLED="$(systemctl is-enabled "$SENSOR_SERVICE" 2>/dev/null || true)"
SENSOR_ACTIVE="$(systemctl is-active "$SENSOR_SERVICE" 2>/dev/null || true)"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

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

restore_collector() {
    if [ "$COLLECTOR_WAS_PRESENT" = true ] && [ -f "$COLLECTOR_BACKUP" ]; then
        install -D -o root -g root -m 0700 "$COLLECTOR_BACKUP" "$COLLECTOR_LIVE"
    else
        rm -f "$COLLECTOR_LIVE"
    fi
}

restore_sensor_state() {
    if [ "$SENSOR_UNIT_WAS_PRESENT" = true ] && [ -f "$SENSOR_UNIT_BACKUP" ]; then
        cp -a "$SENSOR_UNIT_BACKUP" "$SENSOR_UNIT_LIVE"
    else
        rm -f "$SENSOR_UNIT_LIVE"
    fi
    systemctl daemon-reload >/dev/null 2>&1 || true
    case "$SENSOR_ENABLED" in
        enabled|enabled-runtime) systemctl enable "$SENSOR_SERVICE" >/dev/null 2>&1 || true ;;
        *) systemctl disable "$SENSOR_SERVICE" >/dev/null 2>&1 || true ;;
    esac
    if [ "$SENSOR_ACTIVE" = active ]; then
        systemctl start "$SENSOR_SERVICE" >/dev/null 2>&1 || true
    else
        systemctl stop "$SENSOR_SERVICE" >/dev/null 2>&1 || true
    fi
}

refresh_pipeline() {
    systemctl start "$PUSH_SERVICE"
    systemctl start wwcx-security-operations.service
    systemctl start wwcx-security-correlation.service
    systemctl start wwcx-network-defense.service
}

capture_failure_evidence() {
    systemctl status "$LEGACY_SERVICE" "$SENSOR_SERVICE" "$PUSH_SERVICE" --no-pager \
        > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true
    journalctl -u "$LEGACY_SERVICE" -u "$SENSOR_SERVICE" -u "$PUSH_SERVICE" --since=-15min --no-pager \
        > "$EVIDENCE_DIR/failure-service-journal.txt" 2>&1 || true
    ps -eo user,group,pid,ppid,etimes,rss,cmd | grep '[s]uricata' \
        > "$EVIDENCE_DIR/failure-suricata-processes.txt" 2>&1 || true
}

rollback() {
    code=$?
    trap - ERR INT TERM
    set +e
    if [ "$MUTATION_STARTED" = true ]; then
        capture_failure_evidence
        restore_collector
        restore_sensor_state
        restore_legacy_state
        refresh_pipeline >/dev/null 2>&1 || true
        systemctl status "$LEGACY_SERVICE" "$SENSOR_SERVICE" "$PUSH_SERVICE" --no-pager \
            > "$EVIDENCE_DIR/rollback-systemd-status.txt" 2>&1 || true
        printf 'completed_at=%s\naccepted=false\nrolled_back=true\nexit_code=%s\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$code" > "$EVIDENCE_DIR/result.txt"
        printf 'Suricata runtime consolidation failed; previous collector, managed sensor state, and legacy service state restored.\n' >&2
        printf 'Failure evidence: %s\n' "$EVIDENCE_DIR" >&2
    fi
    exit "$code"
}
trap rollback ERR INT TERM

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ -d "$ROOT/.git" ] || fail "repository not found: $ROOT"
for command in awk cmp cp date find git grep hostname install journalctl jq pgrep ps python3 sha256sum stat systemctl tr; do
    command -v "$command" >/dev/null 2>&1 || fail "required command unavailable: $command"
done

HOST="$(hostname -f 2>/dev/null || hostname)"
case "$HOST" in
    edge1|edge1.ww.cx) ;;
    *) fail "consolidation is restricted to Edge1; observed host: $HOST" ;;
esac

[ -n "$EXPECTED_COMMIT" ] || fail "EXPECTED_COMMIT is required"
printf '%s\n' "$EXPECTED_COMMIT" | grep -Eq '^[0-9a-f]{40}$' || fail "EXPECTED_COMMIT must be a full lowercase commit SHA"
[ "$(git -C "$ROOT" branch --show-current)" = main ] || fail "repository must be on main"
[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=all)" ] || fail "repository is not clean"
git -C "$ROOT" merge-base --is-ancestor "$EXPECTED_COMMIT" HEAD || fail "required consolidation commit is missing"
[ -f "$COLLECTOR_SOURCE" ] || fail "collector source is missing"
[ -f "$SENSOR_UNIT_SOURCE" ] || fail "managed sensor unit source is missing"
grep -Fxq 'ExecReload=+/bin/kill -USR2 $MAINPID' "$SENSOR_UNIT_SOURCE" || fail "managed sensor unit source lacks privileged SIGUSR2 rule reload support"

install -d -o root -g root -m 0700 "$EVIDENCE_DIR" "$BACKUP_DIR"
printf '%s\n' "$HOST" > "$EVIDENCE_DIR/host.txt"
printf '%s\n' "$EXPECTED_COMMIT" > "$EVIDENCE_DIR/expected-commit.txt"
git -C "$ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$ROOT" status --short --branch > "$EVIDENCE_DIR/git-status.txt"
printf 'legacy_enabled=%s\nlegacy_active=%s\nsensor_enabled=%s\nsensor_active=%s\n' \
    "$LEGACY_ENABLED" "$LEGACY_ACTIVE" "$SENSOR_ENABLED" "$SENSOR_ACTIVE" \
    > "$EVIDENCE_DIR/service-state-before.txt"
systemctl status "$LEGACY_SERVICE" "$SENSOR_SERVICE" --no-pager \
    > "$EVIDENCE_DIR/systemd-status-before.txt" 2>&1 || true
journalctl -u "$LEGACY_SERVICE" --since=-24h --no-pager \
    > "$EVIDENCE_DIR/legacy-journal-before.txt" 2>&1 || true
ps -eo user,group,pid,ppid,etimes,rss,cmd | grep '[s]uricata' \
    > "$EVIDENCE_DIR/suricata-processes-before.txt" || true

systemctl is-active --quiet "$SENSOR_SERVICE" || fail "$SENSOR_SERVICE is not active"
systemctl is-enabled --quiet "$SENSOR_SERVICE" || fail "$SENSOR_SERVICE is not enabled"
[ -s /var/log/wwcx-network-sensor/suricata/eve.json ] || fail "managed sensor EVE log is absent or empty"

LATEST_SENSOR_EVIDENCE="$(find /var/lib/wwcx-deployment-evidence/network-sensor -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
[ -n "$LATEST_SENSOR_EVIDENCE" ] || fail "network sensor evidence is unavailable"
jq -e '.result == "pass" and .capture_validated == true and .suricata.decoder_packets > 0' \
    "$LATEST_SENSOR_EVIDENCE/suricata-capture-acceptance.json" \
    > "$EVIDENCE_DIR/network-sensor-capture-acceptance.json"

python3 - "$COLLECTOR_SOURCE" <<'PY'
import importlib.util
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("bigbird_ops_collect", path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
assert module.SURICATA_SERVICE == "wwcx-network-sensor-suricata.service"
assert str(module.EVE) == "/var/log/wwcx-network-sensor/suricata/eve.json"
security = module.suricata()
assert security["available"] is True
assert security["service"] == module.SURICATA_SERVICE
assert security["source_path"] == str(module.EVE)
assert security["source_release"] == "edge1-suricata-sensor-consolidation-r1"
PY

python3 "$ROOT/tests/validate_bigbird_ops_collector_suricata.py"
python3 "$ROOT/tests/validate_suricata_runtime_consolidation.py"
python3 -m py_compile "$COLLECTOR_SOURCE"
bash -n "$ROOT/deploy/consolidate-edge1-suricata-runtime.sh"
sh -n "$ROOT/deploy/consolidate-edge1-suricata-runtime.sh"

if [ -f "$COLLECTOR_LIVE" ]; then
    cp -a "$COLLECTOR_LIVE" "$COLLECTOR_BACKUP"
    COLLECTOR_WAS_PRESENT=true
    sha256sum "$COLLECTOR_LIVE" > "$EVIDENCE_DIR/runtime-collector-before.sha256"
fi
if [ -e "$SENSOR_UNIT_LIVE" ]; then
    cp -a "$SENSOR_UNIT_LIVE" "$SENSOR_UNIT_BACKUP"
    SENSOR_UNIT_WAS_PRESENT=true
    sha256sum "$SENSOR_UNIT_LIVE" > "$EVIDENCE_DIR/managed-unit-before.sha256"
fi

MUTATION_STARTED=true
install -D -o root -g root -m 0700 "$COLLECTOR_SOURCE" "$COLLECTOR_LIVE"
cmp -s "$COLLECTOR_SOURCE" "$COLLECTOR_LIVE"
sha256sum "$COLLECTOR_SOURCE" "$COLLECTOR_LIVE" > "$EVIDENCE_DIR/runtime-collector-after.sha256"

install -D -o root -g root -m 0644 "$SENSOR_UNIT_SOURCE" "$SENSOR_UNIT_LIVE"
cmp -s "$SENSOR_UNIT_SOURCE" "$SENSOR_UNIT_LIVE"
systemctl daemon-reload
systemctl cat "$SENSOR_SERVICE" > "$EVIDENCE_DIR/managed-unit-after.txt"
grep -Fq 'ExecReload=+/bin/kill -USR2 $MAINPID' "$EVIDENCE_DIR/managed-unit-after.txt" || fail "loaded managed sensor unit lacks privileged SIGUSR2 rule reload support"
sha256sum "$SENSOR_UNIT_SOURCE" "$SENSOR_UNIT_LIVE" > "$EVIDENCE_DIR/managed-unit-after.sha256"

refresh_pipeline

python3 - "$SOURCE_SNAPSHOT" "$EVIDENCE_DIR/source-before-retirement.json" <<'PY'
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
data = json.loads(source.read_text(encoding="utf-8"))
security = data["security"]
assert data["collector_release"] == "edge1-suricata-enrichment-r1"
assert security["available"] is True
assert security["service"] == "wwcx-network-sensor-suricata.service"
assert security["source_path"] == "/var/log/wwcx-network-sensor/suricata/eve.json"
assert security["source_release"] == "edge1-suricata-sensor-consolidation-r1"
service_names = {item.get("name") for item in data.get("services", [])}
assert "wwcx-network-sensor-suricata.service" in service_names
assert "suricata.service" not in service_names
output.write_text(json.dumps({
    "ok": True,
    "collector_release": data["collector_release"],
    "security": security,
    "service_names": sorted(name for name in service_names if name),
}, indent=2) + "\n", encoding="utf-8")
PY

systemctl disable --now "$LEGACY_SERVICE"
systemctl is-active --quiet "$SENSOR_SERVICE"
[ "$(systemctl is-active "$LEGACY_SERVICE" 2>/dev/null || true)" = inactive ]
case "$(systemctl is-enabled "$LEGACY_SERVICE" 2>/dev/null || true)" in
    disabled|not-found) ;;
    *) fail "$LEGACY_SERVICE remains enabled" ;;
esac

SENSOR_PIDS="$(pgrep -x Suricata-Main || true)"
SENSOR_PID_COUNT="$(printf '%s\n' "$SENSOR_PIDS" | awk 'NF {count += 1} END {print count + 0}')"
[ "$SENSOR_PID_COUNT" -eq 1 ] || fail "expected exactly one Suricata main process; observed $SENSOR_PID_COUNT"
set -- $SENSOR_PIDS
SENSOR_PID=$1
tr '\0' ' ' < "/proc/$SENSOR_PID/cmdline" > "$EVIDENCE_DIR/suricata-command-after.txt"
grep -Fq -- '--pcap=' "$EVIDENCE_DIR/suricata-command-after.txt" || fail "remaining Suricata process is not the managed libpcap sensor"
systemctl is-active --quiet "$SENSOR_SERVICE"

refresh_pipeline

python3 - "$SOURCE_SNAPSHOT" "$EVIDENCE_DIR/source-after-retirement.json" <<'PY'
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
data = json.loads(source.read_text(encoding="utf-8"))
security = data["security"]
assert security["available"] is True
assert security["service"] == "wwcx-network-sensor-suricata.service"
assert security["source_path"] == "/var/log/wwcx-network-sensor/suricata/eve.json"
assert security["source_release"] == "edge1-suricata-sensor-consolidation-r1"
services = {item.get("name"): item for item in data.get("services", [])}
managed = services["wwcx-network-sensor-suricata.service"]
assert managed["active"] == "active"
assert "suricata.service" not in services
output.write_text(json.dumps({
    "ok": True,
    "managed_service": managed,
    "security": security,
}, indent=2) + "\n", encoding="utf-8")
PY

jq -e '.overall_state == "observed" and .traffic_controls_changed == false' \
    /var/www/edge1-status/network-defense/data/network-defense.json \
    > "$EVIDENCE_DIR/network-defense-after.json"

systemctl status "$LEGACY_SERVICE" "$SENSOR_SERVICE" "$PUSH_SERVICE" --no-pager \
    > "$EVIDENCE_DIR/systemd-status-after.txt" 2>&1 || true
journalctl -u "$SENSOR_SERVICE" --since=-10min --no-pager \
    > "$EVIDENCE_DIR/managed-sensor-journal-after.txt" 2>&1 || true
ps -eo user,group,pid,ppid,etimes,rss,cmd | grep '[s]uricata' \
    > "$EVIDENCE_DIR/suricata-processes-after.txt"

sha256sum \
    "$EVIDENCE_DIR/source-before-retirement.json" \
    "$EVIDENCE_DIR/source-after-retirement.json" \
    "$EVIDENCE_DIR/network-defense-after.json" \
    "$EVIDENCE_DIR/suricata-command-after.txt" \
    "$EVIDENCE_DIR/managed-unit-after.txt" \
    > "$EVIDENCE_DIR/SHA256SUMS"

printf 'completed_at=%s\naccepted=true\nrolled_back=false\nlegacy_service_disabled=true\nmanaged_sensor_active=true\nmanaged_unit_installed=true\nmanaged_reload_contract_installed=true\ntraffic_controls_changed=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Edge1 Suricata runtime consolidation passed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
