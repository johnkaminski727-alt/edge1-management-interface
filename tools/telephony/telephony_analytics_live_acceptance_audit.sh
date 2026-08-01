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

for command in awk cat curl date dirname find git grep hostname id install python3 runuser sed sha256sum sort ss stat systemctl tr wc xargs; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing command: $command" >&2
        exit 2
    }
done

REPO_OWNER=$(stat -c '%U' "$REPO_ROOT")
REPO_GROUP=$(stat -c '%G' "$REPO_ROOT")
[ -n "$REPO_OWNER" ] || { echo "ERROR repository owner is empty" >&2; exit 2; }

install -d -m 0700 "$EVIDENCE_DIR"
warnings=0
failures=0
runtime_api_source_match=unknown
runtime_platform_source_match=unknown
index_owner_preserved=unknown

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
    if [ "$REPO_OWNER" = "root" ]; then
        git -C "$REPO_ROOT" "$@"
    else
        runuser -u "$REPO_OWNER" -- git -C "$REPO_ROOT" "$@"
    fi
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
printf 'Mode: read-only service, listener, endpoint, source-provenance, privacy, and method-boundary inspection; no install, enable, start, stop, restart, reload, route, call, message, database, carrier, firewall, certificate, DNS, or configuration change\n'
printf 'Repository: %s\n' "$REPO_ROOT"
printf 'Repository owner: %s:%s\n' "$REPO_OWNER" "$REPO_GROUP"
printf 'Evidence directory: %s\n' "$EVIDENCE_DIR"

section "REPOSITORY STATE"
if [ ! -f "$REPO_ROOT/.git/index" ]; then
    fail "repository index is missing"
else
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$REPO_ROOT/.git/index" \
        | tee "$EVIDENCE_DIR/index-before.txt"
    INDEX_OWNER_BEFORE=$(stat -c '%U' "$REPO_ROOT/.git/index")
    INDEX_GROUP_BEFORE=$(stat -c '%G' "$REPO_ROOT/.git/index")
    if [ "$INDEX_OWNER_BEFORE" != "$REPO_OWNER" ] || [ "$INDEX_GROUP_BEFORE" != "$REPO_GROUP" ]; then
        fail "repository index owner does not match repository owner"
    fi
fi

git_repo rev-parse HEAD | tee "$EVIDENCE_DIR/repository-head.txt"
git_repo branch --show-current | tee "$EVIDENCE_DIR/repository-branch.txt"
git_repo status --porcelain >"$EVIDENCE_DIR/repository-status.txt"
if [ -s "$EVIDENCE_DIR/repository-status.txt" ]; then
    fail "repository working tree is not clean"
fi

if [ -f "$REPO_ROOT/.git/index" ]; then
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$REPO_ROOT/.git/index" \
        | tee "$EVIDENCE_DIR/index-after.txt"
    INDEX_OWNER_AFTER=$(stat -c '%U' "$REPO_ROOT/.git/index")
    INDEX_GROUP_AFTER=$(stat -c '%G' "$REPO_ROOT/.git/index")
    if [ "$INDEX_OWNER_AFTER" = "$REPO_OWNER" ] && [ "$INDEX_GROUP_AFTER" = "$REPO_GROUP" ]; then
        index_owner_preserved=yes
    else
        index_owner_preserved=no
        fail "repository index ownership changed during the audit"
    fi
fi
printf 'index_owner_preserved=%s\n' "$index_owner_preserved"

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

section "RUNTIME SOURCE PROVENANCE"
RUNTIME_API_PATH=$(awk '
    /^ExecStart=/ {
        for (field = 1; field <= NF; field++) {
            if ($field ~ /^\/.*\/server\/telephony_analytics_api\.py$/) {
                print $field
                exit
            }
        }
    }
' "$EVIDENCE_DIR/service-properties.txt")

if [ -z "$RUNTIME_API_PATH" ]; then
    fail "runtime analytics API source path could not be parsed from ExecStart"
else
    printf '%s\n' "$RUNTIME_API_PATH" | tee "$EVIDENCE_DIR/runtime-api-path.txt"
    RUNTIME_SERVER_DIR=$(dirname "$RUNTIME_API_PATH")
    RUNTIME_PLATFORM_PATH="$RUNTIME_SERVER_DIR/telephony_platform.py"
    printf '%s\n' "$RUNTIME_PLATFORM_PATH" | tee "$EVIDENCE_DIR/runtime-platform-path.txt"

    if [ ! -f "$RUNTIME_API_PATH" ]; then
        fail "runtime analytics API source file is missing: $RUNTIME_API_PATH"
    fi
    if [ ! -f "$RUNTIME_PLATFORM_PATH" ]; then
        fail "runtime telephony platform source file is missing: $RUNTIME_PLATFORM_PATH"
    fi

    if [ -f "$RUNTIME_API_PATH" ]; then
        stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$RUNTIME_API_PATH" >"$EVIDENCE_DIR/runtime-api-metadata.txt"
        sha256sum "$RUNTIME_API_PATH" >"$EVIDENCE_DIR/runtime-api.sha256"
        cat "$EVIDENCE_DIR/runtime-api-metadata.txt"
        cat "$EVIDENCE_DIR/runtime-api.sha256"
        runtime_api_hash=$(awk '{print $1}' "$EVIDENCE_DIR/runtime-api.sha256")
        repository_api_hash=$(sha256sum "$REPO_ROOT/server/telephony_analytics_api.py" | awk '{print $1}')
        if [ "$runtime_api_hash" = "$repository_api_hash" ]; then
            runtime_api_source_match=yes
        else
            runtime_api_source_match=no
            fail "runtime analytics API source hash differs from the canonical repository"
        fi
    fi

    if [ -f "$RUNTIME_PLATFORM_PATH" ]; then
        stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$RUNTIME_PLATFORM_PATH" >"$EVIDENCE_DIR/runtime-platform-metadata.txt"
        sha256sum "$RUNTIME_PLATFORM_PATH" >"$EVIDENCE_DIR/runtime-platform.sha256"
        cat "$EVIDENCE_DIR/runtime-platform-metadata.txt"
        cat "$EVIDENCE_DIR/runtime-platform.sha256"
        runtime_platform_hash=$(awk '{print $1}' "$EVIDENCE_DIR/runtime-platform.sha256")
        repository_platform_hash=$(sha256sum "$REPO_ROOT/server/telephony_platform.py" | awk '{print $1}')
        if [ "$runtime_platform_hash" = "$repository_platform_hash" ]; then
            runtime_platform_source_match=yes
        else
            runtime_platform_source_match=no
            fail "runtime telephony platform source hash differs from the canonical repository"
        fi
    fi
fi

printf 'runtime_api_source_match=%s\n' "$runtime_api_source_match"
printf 'runtime_platform_source_match=%s\n' "$runtime_platform_source_match"

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
printf 'index_owner_preserved=%s\n' "$index_owner_preserved"
printf 'runtime_api_source_match=%s\n' "$runtime_api_source_match"
printf 'runtime_platform_source_match=%s\n' "$runtime_platform_source_match"
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
