#!/bin/sh
set -eu
umask 077

EXPECTED_HOST="edge1.ww.cx"
REPO_ROOT="/opt/edge1-management-interface"
EVIDENCE_DIR=""
BASE_URL="http://127.0.0.1:8099"
SERVICE="wwcx-telephony-analytics.service"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --expected-host)
            [ "$#" -ge 2 ] || { echo "ERROR missing hostname" >&2; exit 2; }
            EXPECTED_HOST=$2
            shift 2
            ;;
        --repo-root)
            [ "$#" -ge 2 ] || { echo "ERROR missing repository root" >&2; exit 2; }
            REPO_ROOT=$2
            shift 2
            ;;
        --evidence-dir)
            [ "$#" -ge 2 ] || { echo "ERROR missing evidence directory" >&2; exit 2; }
            EVIDENCE_DIR=$2
            shift 2
            ;;
        --base-url)
            [ "$#" -ge 2 ] || { echo "ERROR missing base URL" >&2; exit 2; }
            BASE_URL=$2
            shift 2
            ;;
        -h|--help)
            echo "Usage: sudo $0 --evidence-dir DIR [--expected-host HOST] [--repo-root DIR]"
            echo "Read-only live acceptance audit for the loopback telephony analytics API."
            exit 0
            ;;
        *)
            echo "ERROR unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR run with sudo" >&2; exit 2; }
[ -n "$EVIDENCE_DIR" ] || { echo "ERROR --evidence-dir is required" >&2; exit 2; }
case "$EVIDENCE_DIR" in
    /var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/*) ;;
    *)
        echo "ERROR evidence directory must be below /var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance" >&2
        exit 2
        ;;
esac
case "$BASE_URL" in
    http://127.0.0.1:8099|http://localhost:8099) ;;
    *)
        echo "ERROR base URL must remain loopback-only on port 8099" >&2
        exit 2
        ;;
esac

HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || {
    echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2
    exit 2
}
[ -d "$REPO_ROOT/.git" ] || { echo "ERROR repository not found: $REPO_ROOT" >&2; exit 2; }

for command in awk cat curl date find git grep hostname id install python3 sed sha256sum sort ss stat systemctl tr wc xargs; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing command: $command" >&2
        exit 2
    }
done

install -d -m 0700 "$EVIDENCE_DIR"
warnings=0
failures=0

warn() {
    warnings=$((warnings + 1))
    printf 'WARNING: %s\n' "$*"
}

fail() {
    failures=$((failures + 1))
    printf 'FAIL: %s\n' "$*"
}

section() {
    printf '\n=== %s ===\n' "$*"
}

capture_json() {
    name=$1
    path=$2
    output="$EVIDENCE_DIR/$name.json"
    code=$(curl -sS --max-time 5 -o "$output" -w '%{http_code}' "$BASE_URL$path" || true)
    printf '%s\n' "$code" >"$EVIDENCE_DIR/$name.http-status.txt"
    if [ "$code" != "200" ]; then
        fail "$path returned HTTP $code"
        return
    fi
    if ! python3 -m json.tool "$output" >"$EVIDENCE_DIR/$name.pretty.json" 2>"$EVIDENCE_DIR/$name.json-error.txt"; then
        fail "$path did not return valid JSON"
    fi
}

printf 'WW.CX TELEPHONY ANALYTICS LIVE ACCEPTANCE AUDIT\n'
printf 'Host: %s\n' "$HOST"
printf 'Time: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'Mode: read-only service, listener, endpoint, privacy, and method-boundary inspection; no install, enable, start, stop, restart, reload, route, call, message, database, carrier, firewall, certificate, DNS, or configuration change\n'
printf 'Repository: %s\n' "$REPO_ROOT"
printf 'Evidence directory: %s\n' "$EVIDENCE_DIR"

section "REPOSITORY STATE"
cd "$REPO_ROOT"
git rev-parse HEAD | tee "$EVIDENCE_DIR/repository-head.txt"
git branch --show-current | tee "$EVIDENCE_DIR/repository-branch.txt"
git status --porcelain >"$EVIDENCE_DIR/repository-status.txt"
if [ -s "$EVIDENCE_DIR/repository-status.txt" ]; then
    fail "repository working tree is not clean"
fi

section "SERVICE AND UNIT STATE"
systemctl is-active "$SERVICE" >"$EVIDENCE_DIR/service-active.txt" 2>&1 || true
systemctl is-enabled "$SERVICE" >"$EVIDENCE_DIR/service-enabled.txt" 2>&1 || true
systemctl show "$SERVICE" \
    --property=ActiveState,SubState,UnitFileState,User,Group,ExecStart,FragmentPath,MainPID,NoNewPrivileges,ProtectSystem,ProtectHome,PrivateTmp,MemoryDenyWriteExecute \
    >"$EVIDENCE_DIR/service-properties.txt" 2>&1 || true
cat "$EVIDENCE_DIR/service-active.txt"
cat "$EVIDENCE_DIR/service-enabled.txt"
cat "$EVIDENCE_DIR/service-properties.txt"

if ! grep -Fxq active "$EVIDENCE_DIR/service-active.txt"; then
    fail "$SERVICE is not active"
fi
if ! grep -Eq '^User=wwadmin$' "$EVIDENCE_DIR/service-properties.txt"; then
    fail "$SERVICE does not run as wwadmin"
fi
if ! grep -Eq 'telephony_analytics_api.py --host 127\.0\.0\.1 --port 8099' "$EVIDENCE_DIR/service-properties.txt"; then
    fail "$SERVICE ExecStart is not the expected loopback analytics command"
fi
for property in 'NoNewPrivileges=yes' 'ProtectSystem=strict' 'ProtectHome=yes' 'PrivateTmp=yes' 'MemoryDenyWriteExecute=yes'; do
    if ! grep -Fxq "$property" "$EVIDENCE_DIR/service-properties.txt"; then
        warn "$SERVICE property not confirmed: $property"
    fi
done

section "LISTENER BOUNDARY"
ss -lntp >"$EVIDENCE_DIR/tcp-listeners.txt"
grep -E '(:|\])8099([[:space:]]|$)' "$EVIDENCE_DIR/tcp-listeners.txt" >"$EVIDENCE_DIR/port-8099-listeners.txt" || true
cat "$EVIDENCE_DIR/port-8099-listeners.txt"
if [ ! -s "$EVIDENCE_DIR/port-8099-listeners.txt" ]; then
    fail "no TCP listener found on port 8099"
fi
if grep -E '0\.0\.0\.0:8099|\[::\]:8099|\*:8099' "$EVIDENCE_DIR/port-8099-listeners.txt" >/dev/null; then
    fail "unsafe wildcard listener detected on port 8099"
fi
if ! grep -E '127\.0\.0\.1:8099|\[::1\]:8099' "$EVIDENCE_DIR/port-8099-listeners.txt" >/dev/null; then
    fail "loopback listener was not confirmed on port 8099"
fi

section "READ-ONLY ENDPOINTS"
capture_json healthz /healthz
capture_json platform-health /api/telephony/platform/health
capture_json calls-summary /api/telephony/platform/calls/summary
capture_json interconnects-summary /api/telephony/platform/interconnects/summary

section "METHOD BOUNDARY"
post_code=$(curl -sS --max-time 5 -o "$EVIDENCE_DIR/post-response.json" -w '%{http_code}' -X POST "$BASE_URL/api/telephony/platform/health" || true)
printf '%s\n' "$post_code" | tee "$EVIDENCE_DIR/post.http-status.txt"
if [ "$post_code" != "405" ]; then
    fail "POST method boundary returned HTTP $post_code instead of 405"
fi

section "PAYLOAD CONTRACT AND PRIVACY"
python3 - "$EVIDENCE_DIR" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
errors = []


def load(name):
    try:
        value = json.loads((root / name).read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{name}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{name}: root must be an object")
        return {}
    return value


def require(condition, message):
    if not condition:
        errors.append(message)


def walk(value, location="payload"):
    prohibited_keys = {
        "caller", "caller_id", "callerid", "callee", "called_number", "calling_number",
        "did", "phone", "phone_number", "telephone_number", "extension", "account",
        "account_id", "account_number", "username", "password", "secret", "token",
        "api_key", "credential", "credentials", "sip_uri", "email", "email_address",
        "message_body", "audio", "recording", "recording_path", "source_ip", "destination_ip",
    }
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    sip_uri = re.compile(r"(?i)\bsips?:[^\s]+")
    long_number = re.compile(r"(?<![A-Za-z0-9])\+?[0-9][0-9 ()-]{6,}[0-9](?![A-Za-z0-9])")
    ipv4 = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in prohibited_keys:
                errors.append(f"{location}: prohibited key {key}")
            walk(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, f"{location}[{index}]")
    elif isinstance(value, str):
        if email.search(value):
            errors.append(f"{location}: email-like value")
        if sip_uri.search(value):
            errors.append(f"{location}: SIP URI-like value")
        if ipv4.search(value) and value not in {"127.0.0.1"}:
            errors.append(f"{location}: IP-like value")
        masked = re.sub(r"\b[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?\b", "", value)
        if long_number.search(masked):
            errors.append(f"{location}: long number-like value")

healthz = load("healthz.json")
require(healthz.get("status") == "ok", "healthz.status must be ok")
require(healthz.get("mode") == "read_only", "healthz.mode must be read_only")

health = load("platform-health.json")
require(isinstance(health.get("score"), int) and 0 <= health.get("score", -1) <= 100, "health score must be 0..100")
require(health.get("overall_status") in {"healthy", "degraded", "critical"}, "health overall_status is invalid")
require(isinstance(health.get("components"), dict), "health components must be an object")

calls = load("calls-summary.json")
for key in ("calls_total", "calls_answered", "answer_rate_percent", "duration_seconds_total", "duration_seconds_average"):
    require(isinstance(calls.get(key), (int, float)), f"calls summary missing numeric {key}")
for key in ("directions", "dispositions", "carriers", "destination_countries", "sip_codes", "failure_classes"):
    require(isinstance(calls.get(key), dict), f"calls summary missing object {key}")

interconnects = load("interconnects-summary.json")
require(isinstance(interconnects.get("interconnects_total"), int), "interconnects_total must be an integer")
require(isinstance(interconnects.get("states"), dict), "interconnect states must be an object")
require(isinstance(interconnects.get("attention_required"), int), "attention_required must be an integer")

for filename in ("healthz.json", "platform-health.json", "calls-summary.json", "interconnects-summary.json", "post-response.json"):
    path = root / filename
    if path.is_file():
        try:
            walk(json.loads(path.read_text(encoding="utf-8")), filename)
        except Exception as exc:
            errors.append(f"{filename}: privacy scan failed: {exc}")

(root / "payload-validation.txt").write_text(
    "payload_validation=passed\nprivacy_scan=passed\n" if not errors else "\n".join(errors) + "\n",
    encoding="utf-8",
)
if errors:
    for error in errors:
        print(f"FAIL: {error}")
    raise SystemExit(1)
print("payload_validation=passed")
print("privacy_scan=passed")
PY
if [ "$?" -ne 0 ]; then
    fail "payload contract or privacy validation failed"
fi

section "FILE METADATA"
for path in \
    "$REPO_ROOT/server/telephony_analytics_api.py" \
    "$REPO_ROOT/server/telephony_platform.py" \
    "$REPO_ROOT/deploy/telephony/wwcx-telephony-analytics.service"; do
    if [ -f "$path" ]; then
        stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$path"
        sha256sum "$path"
    else
        fail "missing repository asset: $path"
    fi
done >"$EVIDENCE_DIR/repository-assets.txt"
cat "$EVIDENCE_DIR/repository-assets.txt"

section "DECISION"
printf 'warnings=%s\n' "$warnings"
printf 'failures=%s\n' "$failures"
echo "listener_scope=loopback-only"
echo "api_mode=read-only"
echo "write_methods=not-authorized"
echo "database_query_performed=no"
echo "credentials_read=no"
echo "customer_identifiers_retained=no"
echo "call_origination_performed=no"
echo "dtmf_transmission_performed=no"
echo "carrier_route_changed=no"
echo "service_mutation=none"
echo "runtime_mutation=none"

find "$EVIDENCE_DIR" -maxdepth 1 -type f ! -name evidence-files.sha256 -print0 \
    | sort -z \
    | xargs -0 sha256sum >"$EVIDENCE_DIR/evidence-files.sha256"
sha256sum "$EVIDENCE_DIR/evidence-files.sha256" | tee "$EVIDENCE_DIR/evidence-manifest.sha256"

if [ "$failures" -ne 0 ]; then
    echo "telephony_analytics_live_acceptance=failed"
    exit 1
fi

echo "telephony_analytics_live_acceptance=passed"
exit 0
