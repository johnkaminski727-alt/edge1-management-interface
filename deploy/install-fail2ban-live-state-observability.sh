#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATE_ROOT=${EDGE1_FAIL2BAN_STATE_ROOT:-/var/lib/bigbird-security/fail2ban}
STATE_FILE="$STATE_ROOT/live-state.json"
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
NETWORK_DATA="$STATUS_ROOT/network-defense/data/network-defense.json"
UNIT_ROOT=${EDGE1_SYSTEMD_ROOT:-/etc/systemd/system}
STATUS_URL=${EDGE1_STATUS_URL:-http://127.0.0.1/edge1-status}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/fail2ban-live-state}
REQUIRED_COMMIT=${FAIL2BAN_LIVE_STATE_REQUIRED_COMMIT:-a3ea4a9368841468fe539c624a4755ad6295e4ba}
SERVICE=wwcx-fail2ban-live-state.service
TIMER=wwcx-fail2ban-live-state.timer
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
git -C "$REPO_ROOT" merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD || fail "required Fail2ban verifier commit is missing"

for source in \
    "$REPO_ROOT/server/fail2ban_live_state_verifier.py" \
    "$REPO_ROOT/server/network_defense_exporter.py" \
    "$REPO_ROOT/server/network_defense_dns_exporter.py" \
    "$REPO_ROOT/server/network_defense_fail2ban_exporter.py" \
    "$REPO_ROOT/deploy/systemd/$SERVICE" \
    "$REPO_ROOT/deploy/systemd/$TIMER" \
    "$REPO_ROOT/deploy/systemd/$NETWORK_SERVICE" \
    "$REPO_ROOT/tests/validate_fail2ban_live_state_verifier.py" \
    "$REPO_ROOT/tests/test_network_defense_fail2ban_exporter.py" \
    "$REPO_ROOT/tests/validate_fail2ban_live_state_deployer.py"; do
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
    printf 'Deployment failed and saved Fail2ban observability state was restored.\n' >&2
    printf 'Evidence: %s\n' "$EVIDENCE_DIR" >&2
    exit "$code"
}
trap rollback ERR INT TERM

printf '=== REPOSITORY VALIDATION ===\n'
python3 "$REPO_ROOT/tests/validate_fail2ban_live_state_verifier.py"
python3 "$REPO_ROOT/tests/test_network_defense_fail2ban_exporter.py"
python3 "$REPO_ROOT/tests/validate_fail2ban_live_state_deployer.py"
python3 "$REPO_ROOT/tests/test_network_defense_exporter.py"
python3 "$REPO_ROOT/tests/test_network_defense_dns_exporter.py"
python3 "$REPO_ROOT/tests/test_network_defense_runtime_wiring.py"
python3 -m py_compile \
    "$REPO_ROOT/server/fail2ban_live_state_verifier.py" \
    "$REPO_ROOT/server/network_defense_exporter.py" \
    "$REPO_ROOT/server/network_defense_dns_exporter.py" \
    "$REPO_ROOT/server/network_defense_fail2ban_exporter.py"
bash -n "$REPO_ROOT/deploy/install-fail2ban-live-state-observability.sh"

printf '=== INSTALL READ-ONLY VERIFIER ===\n'
MUTATION_STARTED=1
install -d -o root -g root -m 0755 "$STATE_ROOT"
install -d -o root -g root -m 0755 "$STATUS_ROOT/network-defense/data"
install -m 0644 "$REPO_ROOT/deploy/systemd/$SERVICE" "$UNIT_ROOT/$SERVICE"
install -m 0644 "$REPO_ROOT/deploy/systemd/$TIMER" "$UNIT_ROOT/$TIMER"
install -m 0644 "$REPO_ROOT/deploy/systemd/$NETWORK_SERVICE" "$UNIT_ROOT/$NETWORK_SERVICE"
systemctl daemon-reload
systemctl enable --now "$TIMER"
systemctl start "$SERVICE"

[ "$(systemctl is-enabled "$TIMER")" = enabled ]
[ "$(systemctl is-active "$TIMER")" = active ]
[ "$(systemctl show "$SERVICE" --property=Result --value)" = success ]
[ "$(systemctl show "$SERVICE" --property=ExecMainStatus --value)" = 0 ]
[ -f "$STATE_FILE" ]

printf '=== VERIFY SANITIZED FAIL2BAN STATE ===\n'
python3 - "$STATE_FILE" "$EVIDENCE_DIR/fail2ban-live-state.json" <<'PY'
import ipaddress
import json
import pathlib
import re
import shutil
import sys

source = pathlib.Path(sys.argv[1])
evidence = pathlib.Path(sys.argv[2])
data = json.loads(source.read_text(encoding='utf-8'))
assert data['contract'] == 'wwcx.fail2ban-live-state.v1'
assert data['read_only'] is True
assert data['traffic_controls_changed'] is False
privacy = data['privacy']
for key in (
    'banned_addresses_included', 'log_paths_included', 'raw_client_output_included',
    'commands_included', 'credentials_included', 'private_keys_included',
):
    assert privacy[key] is False
assert data['observation']['enforcement_verified'] is False
assert data['observation']['state'] in {
    'active_observed', 'partial', 'inactive', 'not_installed', 'unavailable'
}
for forbidden_key in ('banned_ips', 'banned_ip_list', 'log_paths', 'raw_output', 'commands'):
    assert forbidden_key not in data

def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)

for text in strings(data):
    for token in re.split(r'[\s,]+', text):
        candidate = token.strip('[](){};')
        if not candidate:
            continue
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        raise AssertionError('published Fail2ban snapshot contains an IP address')

shutil.copy2(source, evidence)
print(json.dumps({
    'ok': True,
    'state': data['observation']['state'],
    'jail_health_observed': data['observation']['jail_health_observed'],
    'jail_count': data['jails']['observed_count'],
    'currently_banned': data['jails']['aggregate']['currently_banned'],
    'total_banned': data['jails']['aggregate']['total_banned'],
    'service_active': data['service']['active'],
    'socket_reachable': data['client']['socket_reachable'],
    'enforcement_verified': data['observation']['enforcement_verified'],
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
component = defense['components']['fail2ban']
assert defense['read_only'] is True
assert defense['traffic_controls_changed'] is False
assert defense['privacy']['fail2ban_banned_addresses_included'] is False
assert defense['privacy']['fail2ban_raw_client_output_included'] is False
assert component['enforcement_verified'] is False
assert component['state'] == live['observation']['state']
assert component['metrics']['observed_jails'] == live['jails']['observed_count']
assert component['metrics']['currently_banned'] == live['jails']['aggregate']['currently_banned']
assert defense['summary']['verified_enforcement_count'] == sum(
    1 for item in defense['components'].values() if item.get('enforcement_verified')
)
assert defense['dns_policy']['enforcement_enabled'] is False
assert defense['dns_policy']['traffic_controls_changed'] is False
summary = {
    'ok': True,
    'fail2ban_state': component['state'],
    'fail2ban_health_observed': component['observed'],
    'fail2ban_enforcement_verified': component['enforcement_verified'],
    'observed_jails': component['metrics']['observed_jails'],
    'currently_banned': component['metrics']['currently_banned'],
    'total_banned': component['metrics']['total_banned'],
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
    "$EVIDENCE_DIR/acceptance-summary.json" > "$EVIDENCE_DIR/sha256.txt"
printf 'completed_at=%s\naccepted=true\nrolled_back=false\nread_only=true\ntraffic_controls_changed=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Fail2ban live-state observability deployment passed.\n'
printf 'Live URL: %s/network-defense/\n' "$STATUS_URL"
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'The verifier made no Fail2ban, nftables, firewall, DNS, routing, proxy, IDS, authentication, or traffic-control changes.\n'
