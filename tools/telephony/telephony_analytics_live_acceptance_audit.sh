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

git_repo() {
    git -c safe.directory="$REPO_ROOT" "$@"
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
git_repo rev-parse HEAD | tee "$EVIDENCE_DIR/repository-head.txt"
git_repo branch --show-current | tee "$EVIDENCE_DIR/repository-branch.txt"
git_repo status --porcelain >"$EVIDENCE_DIR/repository-status.txt"
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

if ! grep -Fxq enabled "$EVIDENCE_DIR/service-enabled.txt"; then
    warn "$SERVICE is active but not confirmed enabled at boot"
fi
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
if ! python3 "$REPO_ROOT/tools/telephony/validate_telephony_analytics_evidence.py" "$EVIDENCE_DIR"; then
    fail "payload contract or privacy validation failed"
fi

section "FILE METADATA"
for path in \
    "$REPO_ROOT/server/telephony_analytics_api.py" \
    "$REPO_ROOT/server/telephony_platform.py" \
    "$REPO_ROOT/tools/telephony/validate_telephony_analytics_evidence.py" \
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
