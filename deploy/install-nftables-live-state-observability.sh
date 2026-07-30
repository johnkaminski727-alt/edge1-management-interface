#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATE_ROOT=${EDGE1_NFTABLES_STATE_ROOT:-/var/lib/bigbird-networking/nftables}
STATE_FILE="$STATE_ROOT/live-state.json"
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
NETWORK_DATA="$STATUS_ROOT/network-defense/data/network-defense.json"
UNIT_ROOT=${EDGE1_SYSTEMD_ROOT:-/etc/systemd/system}
STATUS_URL=${EDGE1_STATUS_URL:-http://127.0.0.1/edge1-status}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/nftables-live-state}
REQUIRED_COMMIT=${NFTABLES_LIVE_STATE_REQUIRED_COMMIT:-455beccdc5dee5f1162059d7a7f3cca055451e07}
SERVICE=wwcx-nftables-live-state.service
TIMER=wwcx-nftables-live-state.timer
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
for command in bash curl date git install journalctl python3 sha256sum stat systemctl; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

HOST=$(hostname -f 2>/dev/null || hostname)
case "$HOST" in
    edge1|edge1.ww.cx) ;;
    *) fail "deployment is restricted to Edge1; observed host: $HOST" ;;
esac

[ "$(git -C "$REPO_ROOT" branch --show-current)" = main ] || fail "deployment requires main"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository has uncommitted or untracked work"
git -C "$REPO_ROOT" merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD || fail "required nftables verifier commit is missing"

for source in \
    "$REPO_ROOT/server/nftables_live_state_verifier.py" \
    "$REPO_ROOT/server/network_defense_exporter.py" \
    "$REPO_ROOT/server/network_defense_dns_exporter.py" \
    "$REPO_ROOT/server/network_defense_fail2ban_exporter.py" \
    "$REPO_ROOT/server/network_defense_nftables_exporter.py" \
    "$REPO_ROOT/deploy/systemd/$SERVICE" \
    "$REPO_ROOT/deploy/systemd/$TIMER" \
    "$REPO_ROOT/deploy/systemd/$NETWORK_SERVICE" \
    "$REPO_ROOT/tests/validate_nftables_live_state_verifier.py" \
    "$REPO_ROOT/tests/test_network_defense_nftables_exporter.py" \
    "$REPO_ROOT/tests/validate_nftables_live_state_deployer.py"; do
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
    printf 'Deployment failed and saved nftables observability state was restored.\n' >&2
    printf 'Evidence: %s\n' "$EVIDENCE_DIR" >&2
    exit "$code"
}
trap rollback ERR INT TERM

printf '=== REPOSITORY VALIDATION ===\n'
python3 "$REPO_ROOT/tests/validate_nftables_live_state_verifier.py"
python3 "$REPO_ROOT/tests/test_network_defense_nftables_exporter.py"
python3 "$REPO_ROOT/tests/validate_nftables_live_state_deployer.py"
python3 "$REPO_ROOT/tests/validate_spamhaus_live_state_deployer.py"
python3 "$REPO_ROOT/tests/validate_fail2ban_live_state_deployer.py"
python3 "$REPO_ROOT/tests/test_network_defense_exporter.py"
python3 "$REPO_ROOT/tests/test_network_defense_dns_exporter.py"
python3 "$REPO_ROOT/tests/test_network_defense_fail2ban_exporter.py"
python3 "$REPO_ROOT/tests/test_network_defense_runtime_wiring.py"
python3 -m py_compile \
    "$REPO_ROOT/server/nftables_live_state_verifier.py" \
    "$REPO_ROOT/server/network_defense_exporter.py" \
    "$REPO_ROOT/server/network_defense_dns_exporter.py" \
    "$REPO_ROOT/server/network_defense_fail2ban_exporter.py" \
    "$REPO_ROOT/server/network_defense_nftables_exporter.py"
bash -n "$REPO_ROOT/deploy/install-nftables-live-state-observability.sh"

printf '=== INSTALL READ-ONLY VERIFIER ===\n'
MUTATION_STARTED=1
install -d -o root -g root -m 0750 "$STATE_ROOT"
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

printf '=== VERIFY SANITIZED NFTABLES AGGREGATES ===\n'
python3 - "$STATE_FILE" "$EVIDENCE_DIR/nftables-live-state.json" <<'PY'
import ipaddress
import json
import pathlib
import re
import shutil
import stat
import sys

source = pathlib.Path(sys.argv[1])
evidence = pathlib.Path(sys.argv[2])
assert stat.S_IMODE(source.stat().st_mode) == 0o640
data = json.loads(source.read_text(encoding='utf-8'))
assert set(data) == {
    'schema_version', 'contract', 'generated_at', 'read_only',
    'traffic_controls_changed', 'privacy', 'service', 'observation',
    'aggregates', 'errors',
}
assert data['contract'] == 'wwcx.nftables-aggregate-live-state.v1'
assert data['read_only'] is True
assert data['traffic_controls_changed'] is False
privacy = data['privacy']
for key in (
    'addresses_included', 'interfaces_included', 'table_names_included',
    'chain_names_included', 'set_names_included', 'set_elements_included',
    'map_elements_included', 'rule_expressions_included', 'rule_comments_included',
    'rule_handles_included', 'full_ruleset_included', 'raw_command_output_included',
    'credentials_included', 'private_keys_included',
):
    assert privacy[key] is False
assert data['observation']['enforcement_verified'] is False
assert data['observation']['state'] in {
    'ruleset_observed', 'partial', 'empty', 'not_installed', 'unavailable'
}
assert set(data['aggregates']) == {
    'objects', 'families', 'base_chains', 'rules', 'elements', 'counter_totals'
}
assert set(data['aggregates']['base_chains']) == {'count', 'hooks', 'policies'}
assert set(data['aggregates']['rules']) == {'with_counters', 'with_verdicts', 'verdicts'}
assert set(data['aggregates']['elements']) == {'set_count', 'map_count'}
assert set(data['aggregates']['counter_totals']) == {'statement_count', 'packets', 'bytes'}

for forbidden_key in (
    'tables', 'chains', 'sets', 'maps', 'expressions', 'comments', 'handles',
    'interfaces', 'addresses', 'elements', 'raw_output', 'ruleset',
):
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
        raise AssertionError('published nftables aggregate snapshot contains an IP address')

shutil.copy2(source, evidence)
aggregates = data['aggregates']
print(json.dumps({
    'ok': True,
    'state': data['observation']['state'],
    'observed': data['observation']['observed'],
    'tables': aggregates['objects']['table'],
    'chains': aggregates['objects']['chain'],
    'rules': aggregates['objects']['rule'],
    'sets': aggregates['objects']['set'],
    'maps': aggregates['objects']['map'],
    'base_chains': aggregates['base_chains']['count'],
    'counter_packets': aggregates['counter_totals']['packets'],
    'counter_bytes': aggregates['counter_totals']['bytes'],
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
component = defense['components']['firewall']
aggregates = live['aggregates']
assert defense['read_only'] is True
assert defense['traffic_controls_changed'] is False
for key in (
    'firewall_addresses_included', 'firewall_interfaces_included',
    'firewall_names_included', 'firewall_rule_expressions_included',
    'firewall_comments_included', 'firewall_handles_included',
):
    assert defense['privacy'][key] is False
assert component['enforcement_verified'] is False
assert component['state'] == live['observation']['state']
assert component['metrics']['tables'] == aggregates['objects']['table']
assert component['metrics']['chains'] == aggregates['objects']['chain']
assert component['metrics']['rules'] == aggregates['objects']['rule']
assert component['metrics']['counter_packets'] == aggregates['counter_totals']['packets']
assert defense['summary']['verified_enforcement_count'] == sum(
    1 for item in defense['components'].values() if item.get('enforcement_verified')
)
assert defense['summary']['verified_enforcement_count'] >= 1
assert defense['dns_policy']['enforcement_enabled'] is False
assert defense['dns_policy']['traffic_controls_changed'] is False
summary = {
    'ok': True,
    'nftables_state': component['state'],
    'nftables_observed': component['observed'],
    'nftables_enforcement_verified': component['enforcement_verified'],
    'tables': component['metrics']['tables'],
    'chains': component['metrics']['chains'],
    'base_chains': component['metrics']['base_chains'],
    'rules': component['metrics']['rules'],
    'sets': component['metrics']['sets'],
    'maps': component['metrics']['maps'],
    'counter_packets': component['metrics']['counter_packets'],
    'counter_bytes': component['metrics']['counter_bytes'],
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
printf 'nftables aggregate live-state observability deployment passed.\n'
printf 'Live URL: %s/network-defense/\n' "$STATUS_URL"
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'The verifier made no nftables, firewall, DNS, routing, Fail2ban, proxy, IDS, authentication, or traffic-control changes.\n'
