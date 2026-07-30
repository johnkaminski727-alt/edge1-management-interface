#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
UNIT_ROOT=${EDGE1_SYSTEMD_ROOT:-/etc/systemd/system}
STATUS_FILE=${EDGE1_NETWORK_DEFENSE_STATUS_FILE:-/var/www/edge1-status/network-defense/data/network-defense.json}
LOCAL_URL=${EDGE1_NETWORK_DEFENSE_LOCAL_URL:-http://127.0.0.1/edge1-status/network-defense/data/network-defense.json}
PUBLIC_URL=${EDGE1_NETWORK_DEFENSE_PUBLIC_URL:-https://edge1.ww.cx/edge1-status/network-defense/data/network-defense.json}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/network-defense-freshness}
REQUIRED_COMMIT=${NETWORK_DEFENSE_FRESHNESS_REQUIRED_COMMIT:-711952afb053fa3bd50c390516fa7b58f3943985}
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
for command in bash git install systemctl python3 cmp sha256sum curl cp rm mkdir hostname id; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
[ "$BRANCH" = main ] || fail "activation requires main; current branch is $BRANCH"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository has uncommitted or untracked work; preserve it before activation"
git -C "$REPO_ROOT" merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD || fail "main does not contain required freshness merge $REQUIRED_COMMIT"

SOURCE_UNIT="$REPO_ROOT/deploy/systemd/$SERVICE"
SOURCE_WRAPPER="$REPO_ROOT/server/network_defense_freshness_exporter.py"
TARGET_UNIT="$UNIT_ROOT/$SERVICE"
for source in "$SOURCE_UNIT" "$SOURCE_WRAPPER" "$REPO_ROOT/tools/networking/validate-network-defense.sh"; do
    [ -f "$source" ] || fail "required source is missing: $source"
done

install -d -o root -g root -m 0700 "$BACKUP_DIR"
printf '%s\n' "$STAMP" > "$EVIDENCE_DIR/started-at.txt"
hostname -f > "$EVIDENCE_DIR/hostname.txt" 2>&1 || hostname > "$EVIDENCE_DIR/hostname.txt"
id > "$EVIDENCE_DIR/principal.txt"
git -C "$REPO_ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$REPO_ROOT" status --short --branch > "$EVIDENCE_DIR/git-status-before.txt"
printf '%s\n' "$STATUS_FILE" > "$EVIDENCE_DIR/status-file.txt"
printf '%s\n' "$LOCAL_URL" > "$EVIDENCE_DIR/local-url.txt"
printf '%s\n' "$PUBLIC_URL" > "$EVIDENCE_DIR/public-url.txt"

backup_file() {
    local path=$1
    local label=$2
    if [ -f "$path" ]; then
        cp -a "$path" "$BACKUP_DIR/$label"
        printf 'present\n' > "$BACKUP_DIR/$label.state"
    else
        printf 'absent\n' > "$BACKUP_DIR/$label.state"
    fi
}

restore_file() {
    local path=$1
    local label=$2
    local state
    state=$(cat "$BACKUP_DIR/$label.state" 2>/dev/null || printf 'absent')
    if [ "$state" = present ]; then
        install -d -m 0755 "$(dirname "$path")"
        cp -a "$BACKUP_DIR/$label" "$path"
    else
        rm -f "$path"
    fi
}

TIMER_ENABLED_BEFORE=$(systemctl is-enabled "$TIMER" 2>/dev/null || true)
TIMER_ACTIVE_BEFORE=$(systemctl is-active "$TIMER" 2>/dev/null || true)
printf '%s\n' "$TIMER_ENABLED_BEFORE" > "$EVIDENCE_DIR/timer-enabled-before.txt"
printf '%s\n' "$TIMER_ACTIVE_BEFORE" > "$EVIDENCE_DIR/timer-active-before.txt"
systemctl cat "$SERVICE" > "$EVIDENCE_DIR/service-unit-before.txt" 2>&1 || true
systemctl status "$SERVICE" "$TIMER" --no-pager > "$EVIDENCE_DIR/systemd-status-before.txt" 2>&1 || true
backup_file "$TARGET_UNIT" service.unit
backup_file "$STATUS_FILE" network-defense.json

python3 - "$STATUS_FILE" "$EVIDENCE_DIR/baseline.json" <<'PY'
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
result = {"present": source.is_file(), "verified_enforcement_count": None}
if source.is_file():
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
        result.update({
            "overall_state": document.get("overall_state"),
            "verified_enforcement_count": (document.get("summary") or {}).get("verified_enforcement_count"),
            "network_stale_after_seconds": ((document.get("sources") or {}).get("network") or {}).get("stale_after_seconds"),
            "dns_policy_state": ((document.get("components") or {}).get("dns_policy") or {}).get("state"),
            "dns_enforcement_enabled": (document.get("dns_policy") or {}).get("enforcement_enabled"),
            "traffic_controls_changed": document.get("traffic_controls_changed"),
        })
    except Exception as exc:
        result["parse_error_type"] = type(exc).__name__
target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

rollback() {
    local code=$?
    trap - ERR INT TERM
    set +e
    if [ "$MUTATION_STARTED" -eq 1 ]; then
        systemctl status "$SERVICE" "$TIMER" --no-pager > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true
        journalctl -u "$SERVICE" -n 100 --no-pager > "$EVIDENCE_DIR/failure-service-journal.txt" 2>&1 || true
        restore_file "$TARGET_UNIT" service.unit
        restore_file "$STATUS_FILE" network-defense.json
        systemctl daemon-reload >/dev/null 2>&1 || true
        printf 'rolled_back=true\nexit_code=%s\n' "$code" > "$EVIDENCE_DIR/rollback.txt"
        printf 'Activation failed and saved files were restored. Evidence: %s\n' "$EVIDENCE_DIR" >&2
    fi
    exit "$code"
}
trap rollback ERR INT TERM

{
    python3 "$REPO_ROOT/tests/test_network_defense_freshness_policy.py"
    python3 "$REPO_ROOT/tests/test_network_defense_deployment.py"
} 2>&1 | tee "$EVIDENCE_DIR/targeted-tests.txt"
bash "$REPO_ROOT/tools/networking/validate-network-defense.sh" 2>&1 | tee "$EVIDENCE_DIR/network-defense-validation.txt"

MUTATION_STARTED=1
install -o root -g root -m 0644 "$SOURCE_UNIT" "$TARGET_UNIT"
systemctl daemon-reload
systemctl start "$SERVICE"

[ "$(systemctl show "$SERVICE" --property=Result --value)" = success ]
[ "$(systemctl show "$SERVICE" --property=ExecMainStatus --value)" = 0 ]
[ -f "$STATUS_FILE" ]
cmp -s "$SOURCE_UNIT" "$TARGET_UNIT"

TIMER_ENABLED_AFTER=$(systemctl is-enabled "$TIMER" 2>/dev/null || true)
TIMER_ACTIVE_AFTER=$(systemctl is-active "$TIMER" 2>/dev/null || true)
printf '%s\n' "$TIMER_ENABLED_AFTER" > "$EVIDENCE_DIR/timer-enabled-after.txt"
printf '%s\n' "$TIMER_ACTIVE_AFTER" > "$EVIDENCE_DIR/timer-active-after.txt"
[ "$TIMER_ENABLED_AFTER" = "$TIMER_ENABLED_BEFORE" ] || fail "timer enablement changed unexpectedly"
[ "$TIMER_ACTIVE_AFTER" = "$TIMER_ACTIVE_BEFORE" ] || fail "timer active state changed unexpectedly"

python3 - "$STATUS_FILE" "$EVIDENCE_DIR/baseline.json" "$EVIDENCE_DIR/acceptance-summary.json" <<'PY'
import json
import pathlib
import sys

status_path = pathlib.Path(sys.argv[1])
baseline_path = pathlib.Path(sys.argv[2])
summary_path = pathlib.Path(sys.argv[3])
document = json.loads(status_path.read_text(encoding="utf-8"))
baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
network = ((document.get("sources") or {}).get("network") or {})
summary = document.get("summary") or {}
dns = document.get("dns_policy") or {}
dns_component = ((document.get("components") or {}).get("dns_policy") or {})

if network.get("stale_after_seconds") != 600:
    raise SystemExit("network stale threshold is not 600 seconds")
if document.get("traffic_controls_changed") is not False:
    raise SystemExit("traffic_controls_changed must remain false")
if dns.get("enforcement_enabled") is not False:
    raise SystemExit("dns_policy.enforcement_enabled must remain false")
if dns.get("enforcement_verified") is not False:
    raise SystemExit("dns_policy.enforcement_verified must remain false")
if dns.get("traffic_controls_changed") is not False:
    raise SystemExit("dns_policy.traffic_controls_changed must remain false")
if dns_component.get("state") != "not_staged":
    raise SystemExit("DNS policy state must remain not_staged")
before_count = baseline.get("verified_enforcement_count")
after_count = summary.get("verified_enforcement_count")
if before_count is not None and after_count != before_count:
    raise SystemExit("verified_enforcement_count changed unexpectedly")

result = {
    "ok": True,
    "overall_state": document.get("overall_state"),
    "network_stale_after_seconds": 600,
    "verified_enforcement_count_before": before_count,
    "verified_enforcement_count_after": after_count,
    "dns_policy_state": "not_staged",
    "dns_enforcement_enabled": False,
    "traffic_controls_changed": False,
}
summary_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(result, sort_keys=True))
PY

curl -fsS --max-time 15 -D "$EVIDENCE_DIR/local-headers.txt" "$LOCAL_URL" -o "$EVIDENCE_DIR/local-network-defense.json"
curl -fsS --max-time 20 -D "$EVIDENCE_DIR/public-headers.txt" "$PUBLIC_URL" -o "$EVIDENCE_DIR/public-network-defense.json"
python3 - "$EVIDENCE_DIR/local-network-defense.json" "$EVIDENCE_DIR/public-network-defense.json" <<'PY'
import json
import pathlib
import sys
for name in sys.argv[1:]:
    document = json.loads(pathlib.Path(name).read_text(encoding="utf-8"))
    if (((document.get("sources") or {}).get("network") or {}).get("stale_after_seconds")) != 600:
        raise SystemExit(f"{name}: network stale threshold is not 600")
    if document.get("traffic_controls_changed") is not False:
        raise SystemExit(f"{name}: traffic_controls_changed is not false")
PY

systemctl cat "$SERVICE" > "$EVIDENCE_DIR/service-unit-after.txt"
systemctl status "$SERVICE" "$TIMER" --no-pager > "$EVIDENCE_DIR/systemd-status-after.txt" 2>&1 || true
journalctl -u "$SERVICE" -n 100 --no-pager > "$EVIDENCE_DIR/service-journal.txt" 2>&1 || true
git -C "$REPO_ROOT" status --short --branch > "$EVIDENCE_DIR/git-status-after.txt"
sha256sum "$SOURCE_WRAPPER" "$SOURCE_UNIT" "$TARGET_UNIT" "$STATUS_FILE" > "$EVIDENCE_DIR/sha256.txt"
printf 'completed_at=%s\nrolled_back=false\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Network Defense freshness activation passed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'Timer state, enforcement count, DNS policy, and traffic-control state are unchanged.\n'
