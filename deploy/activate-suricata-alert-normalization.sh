#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REQUIRED_COMMIT="${SURICATA_NORMALIZATION_REQUIRED_COMMIT:-be2880d49ab842b1876e6c2898f1acced6bb78f1}"
STATUS_URL="${EDGE1_STATUS_URL:-https://edge1.ww.cx/edge1-status}"
EVIDENCE_ROOT="${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/suricata-alert-normalization}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="${1:-$EVIDENCE_ROOT/$STAMP}"
LIVE_PAGE="/var/www/edge1-status/security/index.html"
LIVE_SECURITY="/var/www/edge1-status/security-operations.json"
LIVE_CORRELATION="/var/www/edge1-status/security/correlation/data/security-correlation.json"
LIVE_DEFENSE="/var/www/edge1-status/network-defense/data/network-defense.json"
PAGE_BACKUP="$EVIDENCE_DIR/security-index.before.html"

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

install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
printf '%s\n' "$HOST" > "$EVIDENCE_DIR/host.txt"
printf '%s\n' "$(id -un)" > "$EVIDENCE_DIR/principal.txt"
git -C "$ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$ROOT" status --short --branch > "$EVIDENCE_DIR/git-status.txt"

capture_failure() {
    local code=$?
    trap - ERR INT TERM
    set +e

    if [ -f "$PAGE_BACKUP" ]; then
        install -D -m 0644 "$PAGE_BACKUP" "$LIVE_PAGE"
    fi

    systemctl status \
        wwcx-security-operations.service \
        wwcx-security-operations.timer \
        wwcx-security-correlation.service \
        wwcx-security-correlation.timer \
        wwcx-network-defense.service \
        wwcx-network-defense.timer \
        --no-pager > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true

    for service in security-operations security-correlation network-defense; do
        journalctl -u "wwcx-$service.service" -n 80 --no-pager \
            > "$EVIDENCE_DIR/failure-$service-journal.txt" 2>&1 || true
    done

    printf 'completed_at=%s\naccepted=false\npage_rolled_back=%s\nexit_code=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$([ -f "$PAGE_BACKUP" ] && printf true || printf false)" \
        "$code" > "$EVIDENCE_DIR/result.txt"

    printf 'Suricata normalization activation failed.\n' >&2
    printf 'Failure evidence: %s\n' "$EVIDENCE_DIR" >&2
    exit "$code"
}
trap capture_failure ERR INT TERM

printf '=== PREFLIGHT ===\n'
[ "$(git -C "$ROOT" branch --show-current)" = main ] || fail "repository must be on main"
git -C "$ROOT" merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD || fail "required normalization commit is missing"

for path in \
    server/security_operations_exporter.py \
    src/web/security/index.html \
    tests/validate_security_operations_cache.py \
    tests/validate_security_operations_normalization.py \
    tests/validate_security_operations_ui.py; do
    git -C "$ROOT" diff --quiet -- "$path" || fail "unstaged change detected in $path"
    git -C "$ROOT" diff --cached --quiet -- "$path" || fail "staged change detected in $path"
done

if [ -f "$LIVE_PAGE" ]; then
    cp -a "$LIVE_PAGE" "$PAGE_BACKUP"
fi
for source in "$LIVE_SECURITY" "$LIVE_CORRELATION" "$LIVE_DEFENSE"; do
    if [ -f "$source" ]; then
        cp -a "$source" "$EVIDENCE_DIR/$(basename "$source").before"
    fi
done

printf '=== REPOSITORY VALIDATION ===\n'
python3 "$ROOT/tests/validate_security_operations_cache.py"
python3 "$ROOT/tests/validate_security_operations_normalization.py"
python3 "$ROOT/tests/validate_security_operations_ui.py"
python3 -m py_compile \
    "$ROOT/server/security_operations_exporter.py" \
    "$ROOT/server/security_correlation_exporter.py" \
    "$ROOT/server/network_defense_exporter.py" \
    "$ROOT/server/network_defense_dns_exporter.py"

python3 - "$ROOT/src/web/security/index.html" "$EVIDENCE_DIR/security-inline.js" <<'PY'
from pathlib import Path
import sys

page = Path(sys.argv[1]).read_text(encoding="utf-8")
start = page.index("<script>") + len("<script>")
end = page.index("</script>", start)
Path(sys.argv[2]).write_text(page[start:end], encoding="utf-8")
PY
if command -v node >/dev/null 2>&1; then
    node --check "$EVIDENCE_DIR/security-inline.js" | tee "$EVIDENCE_DIR/node-check.txt"
else
    printf 'node unavailable on Edge1; inline JavaScript syntax was validated by exact-head repository CI\n' \
        | tee "$EVIDENCE_DIR/node-check.txt"
fi

printf '=== STAGE EXPORT PIPELINE ===\n'
python3 - "$ROOT" "$EVIDENCE_DIR/staged-security.json" <<'PY'
import importlib.util
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
module_path = root / "server" / "security_operations_exporter.py"
spec = importlib.util.spec_from_file_location("security_operations_exporter", module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
module.OUTPUT = output
module.write_snapshot(module.live_snapshot())
PY

python3 "$ROOT/server/security_correlation_exporter.py" \
    --security "$EVIDENCE_DIR/staged-security.json" \
    --output "$EVIDENCE_DIR/staged-correlation.json"

python3 "$ROOT/server/network_defense_dns_exporter.py" \
    --security "$EVIDENCE_DIR/staged-security.json" \
    --correlation "$EVIDENCE_DIR/staged-correlation.json" \
    --output "$EVIDENCE_DIR/staged-network-defense.json"

python3 - "$EVIDENCE_DIR" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
security = json.loads((root / "staged-security.json").read_text(encoding="utf-8"))
correlation = json.loads((root / "staged-correlation.json").read_text(encoding="utf-8"))
defense = json.loads((root / "staged-network-defense.json").read_text(encoding="utf-8"))

assert security["schema_version"] == "2.0"
assert security["available"] is True
assert security["cache"]["mode"] == "live"
assert security["cache"]["stale"] is False
assert security["normalization"]["alert_schema"] == "wwcx.suricata-alert.v1"
assert security["normalization"]["raw_events_included"] is False
assert security["normalization"]["packet_payloads_included"] is False

alerts = security["recent_alerts"]
assert isinstance(alerts, list)
assert len(alerts) <= 50
for alert in alerts:
    assert alert["normalization"]["sanitized"] is True
    assert alert["normalization"]["packet_payload_included"] is False
    assert alert["normalization"]["raw_event_included"] is False
    for forbidden in ("payload", "payload_printable", "packet", "raw_event", "credentials", "private_key", "alert"):
        assert forbidden not in alert

assert correlation["read_only"] is True
assert correlation["privacy"]["packet_payloads_included"] is False
assert defense["read_only"] is True
assert defense["traffic_controls_changed"] is False
assert defense["dns_policy"]["enforcement_enabled"] is False
assert defense["dns_policy"]["traffic_controls_changed"] is False
PY

printf '=== PUBLISH AND REFRESH ===\n'
install -D -m 0644 "$ROOT/src/web/security/index.html" "$LIVE_PAGE"

for service in \
    wwcx-security-operations.service \
    wwcx-security-correlation.service \
    wwcx-network-defense.service; do
    systemctl start "$service"
    [ "$(systemctl show "$service" --property=Result --value)" = success ]
    [ "$(systemctl show "$service" --property=ExecMainStatus --value)" = 0 ]
done

printf '=== VERIFY LIVE HTTPS ===\n'
curl -fsS --max-time 20 "$STATUS_URL/security/" > "$EVIDENCE_DIR/security-page.html"
curl -fsS --max-time 20 "$STATUS_URL/security-operations.json" > "$EVIDENCE_DIR/security-operations.json"
curl -fsS --max-time 20 "$STATUS_URL/security-correlation.json" > "$EVIDENCE_DIR/security-correlation.json"
curl -fsS --max-time 20 "$STATUS_URL/network-defense/data/network-defense.json" > "$EVIDENCE_DIR/network-defense.json"

grep -Fq 'Suricata severity' "$EVIDENCE_DIR/security-page.html"
grep -Fq 'Application protocol' "$EVIDENCE_DIR/security-page.html"
grep -Fq 'Source port' "$EVIDENCE_DIR/security-page.html"

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
assert security["normalization"]["alert_schema"] == "wwcx.suricata-alert.v1"
alerts = security["recent_alerts"]
assert isinstance(alerts, list)
assert len(alerts) <= 50

unknown_titles = {"Unclassified Suricata alert", "Unknown IDS signature", "Unknown signature"}
summary = {
    "ok": True,
    "alert_count": len(alerts),
    "classified_alert_count": sum(1 for item in alerts if item.get("signature") not in unknown_titles),
    "known_risk_count": sum(1 for item in alerts if item.get("risk") != "unknown"),
    "source_port_count": sum(1 for item in alerts if item.get("source_port") is not None),
    "destination_port_count": sum(1 for item in alerts if item.get("destination_port") is not None),
    "application_protocol_count": sum(1 for item in alerts if item.get("app_protocol") or item.get("application_protocol")),
    "signature_id_count": sum(1 for item in alerts if item.get("signature_id") is not None),
    "cache_mode": security["cache"]["mode"],
    "cache_stale": security["cache"]["stale"],
    "schema_version": security["schema_version"],
    "alert_schema": security["normalization"]["alert_schema"],
    "correlation_events": (correlation.get("summary") or {}).get("event_count"),
    "correlations": (correlation.get("summary") or {}).get("correlation_count"),
    "network_defense_state": defense.get("overall_state"),
    "traffic_controls_changed": defense["traffic_controls_changed"],
}
assert correlation["read_only"] is True
assert defense["read_only"] is True
assert defense["traffic_controls_changed"] is False
assert defense["dns_policy"]["enforcement_enabled"] is False
print(json.dumps(summary, indent=2))
(root / "acceptance-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
PY

printf '=== OBSERVABILITY ACCEPTANCE ===\n'
bash "$ROOT/tools/security/verify-security-observability-live.sh" \
    "$EVIDENCE_DIR/observability-acceptance"

systemctl status \
    wwcx-security-operations.service \
    wwcx-security-operations.timer \
    wwcx-security-correlation.service \
    wwcx-security-correlation.timer \
    wwcx-network-defense.service \
    wwcx-network-defense.timer \
    --no-pager > "$EVIDENCE_DIR/systemd-status.txt" 2>&1 || true

sha256sum \
    "$EVIDENCE_DIR/security-page.html" \
    "$EVIDENCE_DIR/security-operations.json" \
    "$EVIDENCE_DIR/security-correlation.json" \
    "$EVIDENCE_DIR/network-defense.json" \
    "$EVIDENCE_DIR/acceptance-summary.json" \
    > "$EVIDENCE_DIR/sha256.txt"

printf 'completed_at=%s\naccepted=true\npage_rolled_back=false\nread_only=true\ntraffic_controls_changed=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Suricata alert normalization activation passed.\n'
printf 'Live URL: %s/security/\n' "$STATUS_URL"
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'No IDS rules, DNS, firewall, routing, Fail2ban, proxy, or traffic controls were changed.\n'
