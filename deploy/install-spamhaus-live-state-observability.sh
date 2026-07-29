#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATE_ROOT=${EDGE1_SPAMHAUS_STATE_ROOT:-/var/lib/bigbird-networking/spamhaus}
STATE_FILE="$STATE_ROOT/live-state.json"
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
NETWORK_DATA="$STATUS_ROOT/network-defense/data/network-defense.json"
UNIT_ROOT=${EDGE1_SYSTEMD_ROOT:-/etc/systemd/system}
STATUS_URL=${EDGE1_STATUS_URL:-http://127.0.0.1/edge1-status}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/spamhaus-live-state}
REQUIRED_COMMIT=${SPAMHAUS_LIVE_STATE_REQUIRED_COMMIT:-55f053388cbe17b98ca1745c361b2d7b39f1a78f}
SERVICE=wwcx-spamhaus-live-state.service
TIMER=wwcx-spamhaus-live-state.timer
NETWORK_SERVICE=wwcx-network-defense.service
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
for command in bash cmp curl date git install journalctl python3 sha256sum systemctl; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

HOST=$(hostname -f 2>/dev/null || hostname)
case "$HOST" in
    edge1|edge1.ww.cx) ;;
    *) fail "deployment is restricted to Edge1; observed host: $HOST" ;;
esac

[ "$(git -C "$REPO_ROOT" branch --show-current)" = main ] || fail "deployment requires main"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository has uncommitted or untracked work"
git -C "$REPO_ROOT" merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD || fail "required Spamhaus verifier commit is missing"

for source in \
    "$REPO_ROOT/server/spamhaus_live_state_verifier.py" \
    "$REPO_ROOT/server/network_defense_exporter.py" \
    "$REPO_ROOT/server/network_defense_dns_exporter.py" \
    "$REPO_ROOT/deploy/systemd/$SERVICE" \
    "$REPO_ROOT/deploy/systemd/$TIMER" \
    "$REPO_ROOT/deploy/systemd/$NETWORK_SERVICE" \
    "$REPO_ROOT/src/web/network-defense/index.html" \
    "$REPO_ROOT/tests/validate_spamhaus_live_state_verifier.py" \
    "$REPO_ROOT/tests/validate_spamhaus_live_state_deployer.py"; do
    [ -f "$source" ] || fail "required source is missing: $source"
done

install -d -o root -g root -m 0700 "$EVIDENCE_DIR" "$BACKUP_DIR"
printf '%s\n' "$HOST" > "$EVIDENCE_DIR/host.txt"
git -C "$REPO_ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$REPO_ROOT" status --short --branch > "$EVIDENCE_DIR/git-status.txt"

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
    state=$(cat "$BACKUP_DIR/$label.state" 2>/dev/null || printf absent)
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

backup_path "$UNIT_ROOT/$SERVICE" verifier-service.unit
backup_path "$UNIT_ROOT/$TIMER" verifier-timer.unit
backup_path "$UNIT_ROOT/$NETWORK_SERVICE" network-defense-service.unit
backup_path "$STATUS_ROOT/network-defense/index.html" network-defense.html
backup_path "$STATE_FILE" live-state.json
backup_path "$NETWORK_DATA" network-defense.json

rollback() {
    local code=$?
    trap - ERR INT TERM
    set +e
    if [ "$MUTATION_STARTED" -eq 1 ]; then
        systemctl status "$SERVICE" "$TIMER" "$NETWORK_SERVICE" --no-pager \
            > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true
        journalctl -u "$SERVICE" -n 100 --no-pager \
            > "$EVIDENCE_DIR/failure-verifier-journal.txt" 2>&1 || true
        systemctl stop "$TIMER" >/dev/null 2>&1 || true
        restore_path "$UNIT_ROOT/$SERVICE" verifier-service.unit
        restore_path "$UNIT_ROOT/$TIMER" verifier-timer.unit
        restore_path "$UNIT_ROOT/$NETWORK_SERVICE" network-defense-service.unit
        restore_path "$STATUS_ROOT/network-defense/index.html" network-defense.html
        restore_path "$STATE_FILE" live-state.json
        restore_path "$NETWORK_DATA" network-defense.json
        systemctl daemon-reload >/dev/null 2>&1 || true
        case "$TIMER_ENABLED_BEFORE" in
            enabled|enabled-runtime) systemctl enable "$TIMER" >/dev/null 2>&1 || true ;;
            *) systemctl disable "$TIMER" >/dev/null 2>&1 || true ;;
        esac
        if [ "$TIMER_ACTIVE_BEFORE" = active ]; then
            systemctl start "$TIMER" >/dev/null 2>&1 || true
        fi
        systemctl start "$NETWORK_SERVICE" >/dev/null 2>&1 || true
    fi
    printf 'completed_at=%s\naccepted=false\nrolled_back=true\nexit_code=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$code" > "$EVIDENCE_DIR/result.txt"
    printf 'Deployment failed and saved verifier state was restored.\n' >&2
    printf 'Evidence: %s\n' "$EVIDENCE_DIR" >&2
    exit "$code"
}
trap rollback ERR INT TERM

printf '=== REPOSITORY VALIDATION ===\n'
python3 "$REPO_ROOT/tests/validate_spamhaus_live_state_verifier.py"
python3 "$REPO_ROOT/tests/validate_spamhaus_live_state_deployer.py"
python3 "$REPO_ROOT/tests/test_network_defense_exporter.py"
python3 "$REPO_ROOT/tests/test_network_defense_dns_exporter.py"
python3 "$REPO_ROOT/tests/test_network_defense_runtime_wiring.py"
python3 -m py_compile \
    "$REPO_ROOT/server/spamhaus_live_state_verifier.py" \
    "$REPO_ROOT/server/network_defense_exporter.py" \
    "$REPO_ROOT/server/network_defense_dns_exporter.py"
bash -n "$REPO_ROOT/deploy/install-spamhaus-live-state-observability.sh"

printf '=== INSTALL READ-ONLY VERIFIER ===\n'
MUTATION_STARTED=1
install -d -o root -g root -m 0755 "$STATE_ROOT"
install -d -o root -g root -m 0755 "$STATUS_ROOT/network-defense"
install -m 0644 "$REPO_ROOT/deploy/systemd/$SERVICE" "$UNIT_ROOT/$SERVICE"
install -m 0644 "$REPO_ROOT/deploy/systemd/$TIMER" "$UNIT_ROOT/$TIMER"
install -m 0644 "$REPO_ROOT/deploy/systemd/$NETWORK_SERVICE" "$UNIT_ROOT/$NETWORK_SERVICE"
install -m 0644 "$REPO_ROOT/src/web/network-defense/index.html" "$STATUS_ROOT/network-defense/index.html"
systemctl daemon-reload
systemctl enable --now "$TIMER"
systemctl start "$SERVICE"

[ "$(systemctl is-enabled "$TIMER")" = enabled ]
[ "$(systemctl is-active "$TIMER")" = active ]
[ "$(systemctl show "$SERVICE" --property=Result --value)" = success ]
[ "$(systemctl show "$SERVICE" --property=ExecMainStatus --value)" = 0 ]
[ -f "$STATE_FILE" ]

printf '=== VERIFY SANITIZED LIVE STATE ===\n'
python3 - "$STATE_FILE" "$EVIDENCE_DIR/spamhaus-live-state.json" <<'PY'
import json
import pathlib
import shutil
import sys

source = pathlib.Path(sys.argv[1])
evidence = pathlib.Path(sys.argv[2])
data = json.loads(source.read_text(encoding='utf-8'))
assert data['contract'] == 'wwcx.spamhaus-live-state.v1'
assert data['read_only'] is True
assert data['traffic_controls_changed'] is False
privacy = data['privacy']
for key in ('addresses_included', 'set_elements_included', 'full_ruleset_included', 'raw_command_output_included'):
    assert privacy[key] is False
assert isinstance(data['enforcement']['verified'], bool)
assert data['enforcement']['state'] in {'active_verified', 'partial', 'not_present', 'unavailable'}
rendered = json.dumps(data)
for forbidden in ('elements', 'nftables', 'payload', 'credentials', 'private_key'):
    assert forbidden not in data
shutil.copy2(source, evidence)
print(json.dumps({
    'ok': True,
    'state': data['enforcement']['state'],
    'verified': data['enforcement']['verified'],
    'table_present': data['table']['present'],
    'drop4_elements': data['sets']['drop4']['element_count'],
    'drop6_elements': data['sets']['drop6']['element_count'],
    'service_result': data['service']['result'],
    'timer_ready': data['timer']['ready'],
    'traffic_controls_changed': data['traffic_controls_changed'],
}, indent=2))
PY

printf '=== REFRESH NETWORK DEFENSE ===\n'
systemctl start "$NETWORK_SERVICE"
[ "$(systemctl show "$NETWORK_SERVICE" --property=Result --value)" = success ]
[ "$(systemctl show "$NETWORK_SERVICE" --property=ExecMainStatus --value)" = 0 ]
[ -f "$NETWORK_DATA" ]

curl -fsS --max-time 20 "$STATUS_URL/network-defense/" > "$EVIDENCE_DIR/network-defense.html"
curl -fsS --max-time 20 "$STATUS_URL/network-defense/data/network-defense.json" > "$EVIDENCE_DIR/network-defense.json"
grep -Fq 'Counts only dedicated sanitized live-state verifiers.' "$EVIDENCE_DIR/network-defense.html"

python3 - "$STATE_FILE" "$EVIDENCE_DIR/network-defense.json" "$EVIDENCE_DIR/acceptance-summary.json" <<'PY'
import json
import pathlib
import sys

live = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
defense = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
component = defense['components']['spamhaus']
assert defense['read_only'] is True
assert defense['traffic_controls_changed'] is False
assert defense['privacy']['full_firewall_ruleset_included'] is False
assert defense['privacy']['firewall_set_elements_included'] is False
assert component['enforcement_verified'] is live['enforcement']['verified']
if live['enforcement']['verified']:
    assert component['state'] == 'active_verified'
    assert defense['summary']['verified_enforcement_count'] >= 1
else:
    assert component['state'] != 'active_verified'
assert defense['dns_policy']['enforcement_enabled'] is False
assert defense['dns_policy']['traffic_controls_changed'] is False
summary = {
    'ok': True,
    'spamhaus_state': component['state'],
    'spamhaus_enforcement_verified': component['enforcement_verified'],
    'verified_enforcement_count': defense['summary']['verified_enforcement_count'],
    'overall_state': defense['overall_state'],
    'available_sources': defense['summary']['available_source_count'],
    'source_count': defense['summary']['source_count'],
    'dns_policy_state': defense['components']['dns_policy']['state'],
    'dns_enforcement_enabled': defense['dns_policy']['enforcement_enabled'],
    'traffic_controls_changed': defense['traffic_controls_changed'],
}
print(json.dumps(summary, indent=2))
pathlib.Path(sys.argv[3]).write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
PY

systemctl status "$SERVICE" "$TIMER" "$NETWORK_SERVICE" --no-pager \
    > "$EVIDENCE_DIR/systemd-status.txt" 2>&1 || true
journalctl -u "$SERVICE" -n 50 --no-pager > "$EVIDENCE_DIR/verifier-journal.txt" 2>&1 || true
sha256sum \
    "$UNIT_ROOT/$SERVICE" \
    "$UNIT_ROOT/$TIMER" \
    "$UNIT_ROOT/$NETWORK_SERVICE" \
    "$STATE_FILE" \
    "$NETWORK_DATA" \
    "$STATUS_ROOT/network-defense/index.html" \
    "$EVIDENCE_DIR/acceptance-summary.json" > "$EVIDENCE_DIR/sha256.txt"
printf 'completed_at=%s\naccepted=true\nrolled_back=false\nread_only=true\ntraffic_controls_changed=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Spamhaus live-state observability deployment passed.\n'
printf 'Live URL: %s/network-defense/\n' "$STATUS_URL"
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'The verifier made no nftables, firewall, DNS, routing, Fail2ban, proxy, or traffic-control changes.\n'
