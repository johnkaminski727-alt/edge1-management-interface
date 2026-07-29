#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REQUIRED_COMMIT="${SURICATA_COLLECTOR_REQUIRED_COMMIT:-02b727fc624df430ec703c8b302145e584308742}"
COLLECTOR_SOURCE="$ROOT/server/bigbird_ops_collect.py"
COLLECTOR_LIVE="/usr/local/libexec/bigbird-ops-collect.py"
PUSH_SERVICE="bigbird-ops-push.service"
PUSH_TIMER="bigbird-ops-push.timer"
SOURCE_SNAPSHOT="/var/lib/bigbird/operations-center/latest.json"
STATUS_URL="${EDGE1_STATUS_URL:-https://edge1.ww.cx/edge1-status}"
EVIDENCE_ROOT="${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="${1:-$EVIDENCE_ROOT/$STAMP}"
BACKUP="$EVIDENCE_DIR/backups"
COLLECTOR_BACKUP="$BACKUP/bigbird-ops-collect.py"
TIMER_WAS_ACTIVE=false
COLLECTOR_WAS_PRESENT=false

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run as root, for example: sudo bash $0"
[ -d "$ROOT/.git" ] || fail "repository not found: $ROOT"

for command in curl date git hostname install journalctl python3 sha256sum systemctl; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

HOST="$(hostname -f 2>/dev/null || hostname)"
case "$HOST" in
    edge1|edge1.ww.cx) ;;
    *) fail "activation is restricted to Edge1; observed host: $HOST" ;;
esac

install -d -o root -g root -m 0700 "$EVIDENCE_DIR" "$BACKUP"
printf '%s\n' "$HOST" > "$EVIDENCE_DIR/host.txt"
printf '%s\n' "$(id -un)" > "$EVIDENCE_DIR/principal.txt"
git -C "$ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$ROOT" status --short --branch > "$EVIDENCE_DIR/git-status.txt"

if systemctl is-active --quiet "$PUSH_TIMER"; then
    TIMER_WAS_ACTIVE=true
fi

if [ -f "$COLLECTOR_LIVE" ]; then
    cp -a "$COLLECTOR_LIVE" "$COLLECTOR_BACKUP"
    COLLECTOR_WAS_PRESENT=true
    sha256sum "$COLLECTOR_LIVE" > "$EVIDENCE_DIR/runtime-collector-before.sha256"
fi

for source in \
    "$SOURCE_SNAPSHOT" \
    /var/www/edge1-status/security-operations.json \
    /var/www/edge1-status/security/correlation/data/security-correlation.json \
    /var/www/edge1-status/network-defense/data/network-defense.json; do
    if [ -f "$source" ]; then
        cp -a "$source" "$BACKUP/$(basename "$source").before"
    fi
done

restore_runtime() {
    if [ "$COLLECTOR_WAS_PRESENT" = true ] && [ -f "$COLLECTOR_BACKUP" ]; then
        install -D -o root -g root -m 0700 "$COLLECTOR_BACKUP" "$COLLECTOR_LIVE"
    else
        rm -f "$COLLECTOR_LIVE"
    fi

    systemctl start "$PUSH_SERVICE" >/dev/null 2>&1 || true
    systemctl start wwcx-security-operations.service >/dev/null 2>&1 || true
    systemctl start wwcx-security-correlation.service >/dev/null 2>&1 || true
    systemctl start wwcx-network-defense.service >/dev/null 2>&1 || true

    if [ "$TIMER_WAS_ACTIVE" = true ]; then
        systemctl start "$PUSH_TIMER" >/dev/null 2>&1 || true
    fi
}

capture_failure() {
    code=$?
    trap - ERR INT TERM
    set +e
    restore_runtime

    systemctl status \
        "$PUSH_SERVICE" \
        "$PUSH_TIMER" \
        wwcx-security-operations.service \
        wwcx-security-correlation.service \
        wwcx-network-defense.service \
        --no-pager > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true

    for service in bigbird-ops-push wwcx-security-operations wwcx-security-correlation wwcx-network-defense; do
        journalctl -u "$service.service" -n 100 --no-pager \
            > "$EVIDENCE_DIR/failure-$service-journal.txt" 2>&1 || true
    done

    printf 'completed_at=%s\naccepted=false\ncollector_rolled_back=true\nexit_code=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$code" > "$EVIDENCE_DIR/result.txt"

    printf 'Suricata collector enrichment failed and the previous collector was restored.\n' >&2
    printf 'Failure evidence: %s\n' "$EVIDENCE_DIR" >&2
    exit "$code"
}
trap capture_failure ERR INT TERM

printf '=== PREFLIGHT ===\n'
[ "$(git -C "$ROOT" branch --show-current)" = main ] || fail "repository must be on main"
git -C "$ROOT" merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD || fail "required collector commit is missing"
[ -f "$COLLECTOR_SOURCE" ] || fail "collector source is missing: $COLLECTOR_SOURCE"

for path in \
    server/bigbird_ops_collect.py \
    tests/validate_bigbird_ops_collector_suricata.py \
    deploy/activate-suricata-collector-enrichment.sh; do
    git -C "$ROOT" diff --quiet -- "$path" || fail "unstaged change detected in $path"
    git -C "$ROOT" diff --cached --quiet -- "$path" || fail "staged change detected in $path"
done

printf '=== REPOSITORY VALIDATION ===\n'
python3 "$ROOT/tests/validate_bigbird_ops_collector_suricata.py"
python3 "$ROOT/tests/validate_security_operations_normalization.py"
python3 "$ROOT/tests/validate_security_operations_cache.py"
python3 -m py_compile \
    "$COLLECTOR_SOURCE" \
    "$ROOT/server/security_operations_exporter.py" \
    "$ROOT/server/security_correlation_exporter.py" \
    "$ROOT/server/network_defense_exporter.py"

printf '=== STAGE LIVE EVE EXTRACTION ===\n'
python3 - "$ROOT" "$EVIDENCE_DIR/staged-source-security.json" <<'PY'
import importlib.util
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
module_path = root / "server" / "bigbird_ops_collect.py"
spec = importlib.util.spec_from_file_location("bigbird_ops_collect", module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
security = module.suricata()
output.write_text(json.dumps(security, indent=2) + "\n", encoding="utf-8")

assert security["alert_schema"] == "wwcx.suricata-source-alert.v1"
assert security["privacy"]["packet_payloads_included"] is False
assert security["privacy"]["raw_events_included"] is False
alerts = security["recent_alerts"]
assert isinstance(alerts, list)
assert len(alerts) <= 100
for alert in alerts:
    for forbidden in (
        "payload", "payload_printable", "packet", "raw_event",
        "credentials", "private_key", "alert", "metadata"
    ):
        assert forbidden not in alert
print(json.dumps({
    "available": security["available"],
    "alerts": len(alerts),
    "source_ports": sum(1 for item in alerts if item.get("source_port") is not None),
    "destination_ports": sum(1 for item in alerts if item.get("destination_port") is not None),
    "application_protocols": sum(1 for item in alerts if item.get("application_protocol")),
    "signature_ids": sum(1 for item in alerts if item.get("signature_id") is not None),
    "generator_ids": sum(1 for item in alerts if item.get("generator_id") is not None),
    "revisions": sum(1 for item in alerts if item.get("revision") is not None),
    "flow_ids": sum(1 for item in alerts if item.get("flow_id") is not None),
}, indent=2))
PY

printf '=== INSTALL COLLECTOR ===\n'
systemctl stop "$PUSH_TIMER"
install -D -o root -g root -m 0700 "$COLLECTOR_SOURCE" "$COLLECTOR_LIVE"
sha256sum "$COLLECTOR_SOURCE" "$COLLECTOR_LIVE" > "$EVIDENCE_DIR/runtime-collector-after.sha256"
cmp -s "$COLLECTOR_SOURCE" "$COLLECTOR_LIVE"

printf '=== PUBLISH SOURCE SNAPSHOT ===\n'
systemctl start "$PUSH_SERVICE"
[ "$(systemctl show "$PUSH_SERVICE" --property=Result --value)" = success ]
[ "$(systemctl show "$PUSH_SERVICE" --property=ExecMainStatus --value)" = 0 ]
[ -f "$SOURCE_SNAPSHOT" ]

python3 - "$SOURCE_SNAPSHOT" "$EVIDENCE_DIR/source-acceptance.json" <<'PY'
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
data = json.loads(source.read_text(encoding="utf-8"))
assert data["collector_release"] == "edge1-suricata-enrichment-r1"
assert data["read_only"] is True
security = data["security"]
assert security["alert_schema"] == "wwcx.suricata-source-alert.v1"
assert security["privacy"]["packet_payloads_included"] is False
assert security["privacy"]["raw_events_included"] is False
alerts = security["recent_alerts"]
assert isinstance(alerts, list)
assert len(alerts) <= 100
for alert in alerts:
    for forbidden in (
        "payload", "payload_printable", "packet", "raw_event",
        "credentials", "private_key", "alert", "metadata"
    ):
        assert forbidden not in alert
summary = {
    "ok": True,
    "collector_release": data["collector_release"],
    "alert_schema": security["alert_schema"],
    "alert_count": len(alerts),
    "source_port_count": sum(1 for item in alerts if item.get("source_port") is not None),
    "destination_port_count": sum(1 for item in alerts if item.get("destination_port") is not None),
    "application_protocol_count": sum(1 for item in alerts if item.get("application_protocol")),
    "signature_id_count": sum(1 for item in alerts if item.get("signature_id") is not None),
    "generator_id_count": sum(1 for item in alerts if item.get("generator_id") is not None),
    "revision_count": sum(1 for item in alerts if item.get("revision") is not None),
    "flow_id_count": sum(1 for item in alerts if item.get("flow_id") is not None),
}
if alerts:
    assert summary["source_port_count"] > 0
    assert summary["destination_port_count"] > 0
    assert summary["signature_id_count"] > 0
    assert summary["generator_id_count"] > 0
    assert summary["revision_count"] > 0
    assert summary["flow_id_count"] > 0
print(json.dumps(summary, indent=2))
output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
PY

printf '=== REFRESH NORMALIZED PIPELINE ===\n'
bash "$ROOT/deploy/activate-suricata-alert-normalization.sh" \
    "$EVIDENCE_DIR/normalization-activation"

printf '=== VERIFY LIVE HTTPS ===\n'
curl -fsS --max-time 20 "$STATUS_URL/security-operations.json" \
    > "$EVIDENCE_DIR/security-operations.json"
curl -fsS --max-time 20 "$STATUS_URL/security-correlation.json" \
    > "$EVIDENCE_DIR/security-correlation.json"
curl -fsS --max-time 20 "$STATUS_URL/network-defense/data/network-defense.json" \
    > "$EVIDENCE_DIR/network-defense.json"

python3 - "$EVIDENCE_DIR" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
security = json.loads((root / "security-operations.json").read_text(encoding="utf-8"))
correlation = json.loads((root / "security-correlation.json").read_text(encoding="utf-8"))
defense = json.loads((root / "network-defense.json").read_text(encoding="utf-8"))

assert security["schema_version"] == "2.0"
assert security["available"] is True
assert security["cache"]["mode"] == "live"
assert security["cache"]["stale"] is False
alerts = security["recent_alerts"]
summary = {
    "ok": True,
    "alert_count": len(alerts),
    "source_port_count": sum(1 for item in alerts if item.get("source_port") is not None),
    "destination_port_count": sum(1 for item in alerts if item.get("destination_port") is not None),
    "application_protocol_count": sum(1 for item in alerts if item.get("app_protocol")),
    "signature_id_count": sum(1 for item in alerts if item.get("signature_id") is not None),
    "generator_id_count": sum(1 for item in alerts if item.get("gid") is not None),
    "revision_count": sum(1 for item in alerts if item.get("rev") is not None),
    "flow_id_count": sum(1 for item in alerts if item.get("flow_id") is not None),
    "correlation_events": (correlation.get("summary") or {}).get("event_count"),
    "correlations": (correlation.get("summary") or {}).get("correlation_count"),
    "network_defense_state": defense.get("overall_state"),
    "traffic_controls_changed": defense["traffic_controls_changed"],
}
if alerts:
    assert summary["source_port_count"] > 0
    assert summary["destination_port_count"] > 0
    assert summary["signature_id_count"] > 0
    assert summary["generator_id_count"] > 0
    assert summary["revision_count"] > 0
    assert summary["flow_id_count"] > 0
assert correlation["read_only"] is True
assert defense["read_only"] is True
assert defense["traffic_controls_changed"] is False
assert defense["dns_policy"]["enforcement_enabled"] is False
print(json.dumps(summary, indent=2))
(root / "acceptance-summary.json").write_text(
    json.dumps(summary, indent=2) + "\n", encoding="utf-8"
)
PY

if [ "$TIMER_WAS_ACTIVE" = true ]; then
    systemctl start "$PUSH_TIMER"
fi

systemctl status \
    "$PUSH_SERVICE" \
    "$PUSH_TIMER" \
    wwcx-security-operations.service \
    wwcx-security-correlation.service \
    wwcx-network-defense.service \
    --no-pager > "$EVIDENCE_DIR/systemd-status.txt" 2>&1 || true

sha256sum \
    "$EVIDENCE_DIR/source-acceptance.json" \
    "$EVIDENCE_DIR/security-operations.json" \
    "$EVIDENCE_DIR/security-correlation.json" \
    "$EVIDENCE_DIR/network-defense.json" \
    "$EVIDENCE_DIR/acceptance-summary.json" \
    > "$EVIDENCE_DIR/sha256.txt"

printf 'completed_at=%s\naccepted=true\ncollector_rolled_back=false\nread_only=true\ntraffic_controls_changed=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Suricata collector enrichment activation passed.\n'
printf 'Live URL: %s/security/\n' "$STATUS_URL"
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'No IDS rules, DNS, firewall, routing, Fail2ban, proxy, or traffic controls were changed.\n'
