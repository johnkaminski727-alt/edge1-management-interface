#!/bin/bash
set -Eeuo pipefail
umask 077

EXPECTED_HOST="edge1.ww.cx"
REPO_ROOT="/opt/edge1-management-interface"
ANALYTICS_SERVICE="wwcx-telephony-analytics.service"
CONSOLE_SERVICE="wwcx-telephony-console.service"
ANALYTICS_UNIT_TARGET="/etc/systemd/system/$ANALYTICS_SERVICE"
ANALYTICS_UNIT_SOURCE="$REPO_ROOT/deploy/telephony/wwcx-telephony-analytics.service"
ANALYTICS_URL="http://127.0.0.1:8099"
CONSOLE_URL="http://127.0.0.1:8096"
EVIDENCE_DIR=""
REQUIRED_COMMIT=""

usage() {
    cat <<'EOF'
Usage: sudo deploy/telephony/telephony-anomaly-api-panel-deploy.sh \
  --required-commit SHA \
  --evidence-dir /var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/TIMESTAMP

Deploys the accepted read-only anomaly API by moving the existing analytics
service to canonical main. The console service is inspected but not restarted.
Any post-mutation failure restores the exact prior analytics unit and restarts it.
EOF
}

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
            ANALYTICS_UNIT_SOURCE="$REPO_ROOT/deploy/telephony/wwcx-telephony-analytics.service"
            shift 2
            ;;
        --required-commit)
            [ "$#" -ge 2 ] || { echo "ERROR missing required commit" >&2; exit 2; }
            REQUIRED_COMMIT=$2
            shift 2
            ;;
        --evidence-dir)
            [ "$#" -ge 2 ] || { echo "ERROR missing evidence directory" >&2; exit 2; }
            EVIDENCE_DIR=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR run with sudo" >&2; exit 2; }
[ -n "$REQUIRED_COMMIT" ] || { echo "ERROR --required-commit is required" >&2; exit 2; }
[ -n "$EVIDENCE_DIR" ] || { echo "ERROR --evidence-dir is required" >&2; exit 2; }
case "$REQUIRED_COMMIT" in
    *[!0-9a-f]*|'') echo "ERROR required commit must be a lowercase hexadecimal Git object name" >&2; exit 2 ;;
esac
case "$EVIDENCE_DIR" in
    /var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/*) ;;
    *) echo "ERROR evidence directory is outside the protected deployment root" >&2; exit 2 ;;
esac

for command in awk bash cat cp curl date dirname find git grep hostname id install node python3 readlink runuser sed sha256sum sleep sort ss stat systemctl tee tr wc xargs; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing command: $command" >&2
        exit 2
    }
done

HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || { echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2; exit 2; }
[ -d "$REPO_ROOT/.git" ] || { echo "ERROR repository not found: $REPO_ROOT" >&2; exit 2; }

REPO_OWNER=$(stat -c '%U' "$REPO_ROOT")
REPO_GROUP=$(stat -c '%G' "$REPO_ROOT")
[ "$REPO_OWNER" != "UNKNOWN" ] || { echo "ERROR repository owner is unknown" >&2; exit 2; }

install -d -m 0700 "$EVIDENCE_DIR"

mutation_started=0
rollback_attempted=0

run_repo() {
    if [ "$REPO_OWNER" = "root" ]; then
        (cd "$REPO_ROOT" && "$@")
    else
        runuser -u "$REPO_OWNER" -- sh -c 'cd "$1" && shift && exec "$@"' sh "$REPO_ROOT" "$@"
    fi
}

git_repo() {
    if [ "$REPO_OWNER" = "root" ]; then
        git -C "$REPO_ROOT" "$@"
    else
        runuser -u "$REPO_OWNER" -- env GIT_OPTIONAL_LOCKS=0 git -C "$REPO_ROOT" "$@"
    fi
}

wait_for_url() {
    url=$1
    attempts=${2:-15}
    attempt=1
    while [ "$attempt" -le "$attempts" ]; do
        if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    return 1
}

rollback() {
    original_rc=$?
    trap - ERR
    if [ "$mutation_started" -eq 1 ] && [ "$rollback_attempted" -eq 0 ]; then
        rollback_attempted=1
        echo
        echo "=== AUTOMATIC ROLLBACK ==="
        echo "trigger_exit_code=$original_rc"
        if [ -f "$EVIDENCE_DIR/analytics-unit-before.service" ]; then
            install -m 0644 "$EVIDENCE_DIR/analytics-unit-before.service" "$ANALYTICS_UNIT_TARGET"
            systemctl daemon-reload
            systemctl restart "$ANALYTICS_SERVICE"
            if wait_for_url "$ANALYTICS_URL/healthz" 15; then
                echo "rollback_health=passed"
            else
                echo "rollback_health=failed"
            fi
            systemctl show "$ANALYTICS_SERVICE" \
                --property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory,FragmentPath \
                >"$EVIDENCE_DIR/analytics-service-after-rollback.txt" 2>&1 || true
            cat "$EVIDENCE_DIR/analytics-service-after-rollback.txt" || true
        else
            echo "rollback_unit_backup=missing"
        fi
        echo "rollback_attempted=yes"
    fi
    exit "$original_rc"
}
trap rollback ERR

printf 'WW.CX TELEPHONY ANOMALY API/PANEL DEPLOYMENT\n'
printf 'Host: %s\n' "$HOST"
printf 'Time: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'Repository: %s\n' "$REPO_ROOT"
printf 'Required commit: %s\n' "$REQUIRED_COMMIT"
printf 'Evidence directory: %s\n' "$EVIDENCE_DIR"
printf 'Mutation boundary: analytics unit replacement and analytics service restart only; console service restart prohibited\n'

echo
echo "=== REPOSITORY PREFLIGHT ==="
[ -f "$REPO_ROOT/.git/index" ] || { echo "ERROR repository index missing" >&2; exit 3; }
[ ! -e "$REPO_ROOT/.git/index.lock" ] || { echo "ERROR repository index lock exists" >&2; exit 3; }
INDEX_OWNER_BEFORE=$(stat -c '%U' "$REPO_ROOT/.git/index")
INDEX_GROUP_BEFORE=$(stat -c '%G' "$REPO_ROOT/.git/index")
[ "$INDEX_OWNER_BEFORE" = "$REPO_OWNER" ] || { echo "ERROR repository index owner mismatch" >&2; exit 3; }
[ "$INDEX_GROUP_BEFORE" = "$REPO_GROUP" ] || { echo "ERROR repository index group mismatch" >&2; exit 3; }
stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$REPO_ROOT/.git/index" | tee "$EVIDENCE_DIR/index-before.txt"

git_repo rev-parse HEAD | tee "$EVIDENCE_DIR/repository-head.txt"
git_repo branch --show-current | tee "$EVIDENCE_DIR/repository-branch.txt"
git_repo status --porcelain >"$EVIDENCE_DIR/repository-status-before.txt"
[ ! -s "$EVIDENCE_DIR/repository-status-before.txt" ] || { echo "ERROR repository is not clean" >&2; exit 3; }
[ "$(cat "$EVIDENCE_DIR/repository-branch.txt")" = "main" ] || { echo "ERROR repository is not on main" >&2; exit 3; }
git_repo cat-file -e "$REQUIRED_COMMIT^{commit}"
git_repo merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD

for path in \
    server/telephony_anomaly_indicators.py \
    server/telephony_analytics_api.py \
    server/telephony_platform.py \
    server/telephony_status_server.py \
    src/web/telephony/index.html \
    src/web/telephony/telephony-anomalies.js \
    src/web/telephony/telephony-anomalies.css \
    tools/telephony/telephony_anomaly_api_panel_live_acceptance_audit.sh \
    tools/telephony/validate_telephony_analytics_evidence.py \
    deploy/telephony/wwcx-telephony-analytics.service; do
    [ -f "$REPO_ROOT/$path" ] || { echo "ERROR missing asset: $path" >&2; exit 3; }
    echo "present=$path"
done

echo
echo "=== REPOSITORY VALIDATION ==="
run_repo python3 tests/validate_telephony_anomaly_indicators.py
run_repo python3 tests/validate_telephony_analytics_api.py
run_repo python3 tests/validate_telephony_analytics_console_panels.py
run_repo python3 tests/validate_telephony_anomaly_api_panel.py
run_repo python3 tests/validate_telephony_anomaly_live_deployment.py
run_repo node --check src/web/telephony/telephony.js
run_repo node --check src/web/telephony/telephony-anomalies.js

echo
echo "=== CONSOLE PRECHECK — NO RESTART ==="
systemctl is-active "$CONSOLE_SERVICE" | tee "$EVIDENCE_DIR/console-active-before.txt"
systemctl show "$CONSOLE_SERVICE" \
    --property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory,FragmentPath,User,Group \
    | tee "$EVIDENCE_DIR/console-service-before.txt"
grep -Fq "$REPO_ROOT/server/telephony_status_server.py" "$EVIDENCE_DIR/console-service-before.txt" || {
    echo "ERROR console does not execute from canonical repository; refusing analytics-only deployment" >&2
    exit 4
}
ss -lntp >"$EVIDENCE_DIR/listeners-before.txt"
grep -E '127\.0\.0\.1:8096|\[::1\]:8096' "$EVIDENCE_DIR/listeners-before.txt" >/dev/null || {
    echo "ERROR loopback console listener not confirmed" >&2
    exit 4
}
if grep -E '0\.0\.0\.0:8096|\[::\]:8096|\*:8096' "$EVIDENCE_DIR/listeners-before.txt" >/dev/null; then
    echo "ERROR unsafe console listener detected" >&2
    exit 4
fi
curl -fsS --max-time 5 "$CONSOLE_URL/healthz" >"$EVIDENCE_DIR/console-healthz-before.json"
curl -fsS --max-time 5 "$CONSOLE_URL/" >"$EVIDENCE_DIR/console-index-before.html"
grep -Fq 'telephony-anomalies.js' "$EVIDENCE_DIR/console-index-before.html"
grep -Fq 'id="analytics-anomalies"' "$EVIDENCE_DIR/console-index-before.html"
curl -fsS --max-time 5 "$CONSOLE_URL/telephony-anomalies.js" >"$EVIDENCE_DIR/telephony-anomalies-before.js"
curl -fsS --max-time 5 "$CONSOLE_URL/telephony-anomalies.css" >"$EVIDENCE_DIR/telephony-anomalies-before.css"

echo
echo "=== ANALYTICS PRECHECK AND ROLLBACK BASELINE ==="
[ -f "$ANALYTICS_UNIT_TARGET" ] || { echo "ERROR analytics unit target missing" >&2; exit 5; }
[ ! -L "$ANALYTICS_UNIT_TARGET" ] || { echo "ERROR analytics unit target is a symlink" >&2; exit 5; }
systemctl is-active "$ANALYTICS_SERVICE" | tee "$EVIDENCE_DIR/analytics-active-before.txt"
systemctl is-enabled "$ANALYTICS_SERVICE" | tee "$EVIDENCE_DIR/analytics-enabled-before.txt"
systemctl show "$ANALYTICS_SERVICE" \
    --property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory,FragmentPath,User,Group,NoNewPrivileges,ProtectSystem,ProtectHome,PrivateTmp,MemoryDenyWriteExecute \
    | tee "$EVIDENCE_DIR/analytics-service-before.txt"
cp --preserve=mode,ownership,timestamps "$ANALYTICS_UNIT_TARGET" "$EVIDENCE_DIR/analytics-unit-before.service"
sha256sum "$ANALYTICS_UNIT_TARGET" | tee "$EVIDENCE_DIR/analytics-unit-before.sha256"
curl -fsS --max-time 5 "$ANALYTICS_URL/healthz" >"$EVIDENCE_DIR/analytics-healthz-before.json"

sed \
    -e "s#WorkingDirectory=/opt/edge1-management-interface#WorkingDirectory=$REPO_ROOT#" \
    -e "s#/opt/edge1-management-interface/server/telephony_analytics_api.py#$REPO_ROOT/server/telephony_analytics_api.py#" \
    "$ANALYTICS_UNIT_SOURCE" >"$EVIDENCE_DIR/analytics-unit-candidate.service"

grep -Fq "WorkingDirectory=$REPO_ROOT" "$EVIDENCE_DIR/analytics-unit-candidate.service"
grep -Fq "ExecStart=/usr/bin/python3 $REPO_ROOT/server/telephony_analytics_api.py --host 127.0.0.1 --port 8099" "$EVIDENCE_DIR/analytics-unit-candidate.service"
for marker in \
    'User=wwadmin' \
    'Group=wwadmin' \
    'NoNewPrivileges=true' \
    'ProtectSystem=strict' \
    'ProtectHome=true' \
    'PrivateTmp=true' \
    'MemoryDenyWriteExecute=true'; do
    grep -Fq "$marker" "$EVIDENCE_DIR/analytics-unit-candidate.service"
done
sha256sum "$EVIDENCE_DIR/analytics-unit-candidate.service" | tee "$EVIDENCE_DIR/analytics-unit-candidate.sha256"

echo
echo "=== BOUNDED ANALYTICS DEPLOYMENT ==="
mutation_started=1
install -m 0644 "$EVIDENCE_DIR/analytics-unit-candidate.service" "$ANALYTICS_UNIT_TARGET"
systemctl daemon-reload
systemctl restart "$ANALYTICS_SERVICE"
wait_for_url "$ANALYTICS_URL/healthz" 15

echo
echo "=== POST-DEPLOYMENT SERVICE VERIFICATION ==="
systemctl is-active "$ANALYTICS_SERVICE" | tee "$EVIDENCE_DIR/analytics-active-after.txt"
systemctl is-enabled "$ANALYTICS_SERVICE" | tee "$EVIDENCE_DIR/analytics-enabled-after.txt"
systemctl show "$ANALYTICS_SERVICE" \
    --property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory,FragmentPath,User,Group,NoNewPrivileges,ProtectSystem,ProtectHome,PrivateTmp,MemoryDenyWriteExecute \
    | tee "$EVIDENCE_DIR/analytics-service-after.txt"
grep -Fq "$REPO_ROOT/server/telephony_analytics_api.py" "$EVIDENCE_DIR/analytics-service-after.txt"
grep -Fq "WorkingDirectory=$REPO_ROOT" "$EVIDENCE_DIR/analytics-service-after.txt"

ss -lntp >"$EVIDENCE_DIR/listeners-after.txt"
grep -E '127\.0\.0\.1:8099|\[::1\]:8099' "$EVIDENCE_DIR/listeners-after.txt" >/dev/null
if grep -E '0\.0\.0\.0:8099|\[::\]:8099|\*:8099' "$EVIDENCE_DIR/listeners-after.txt" >/dev/null; then
    echo "ERROR unsafe analytics listener detected" >&2
    false
fi

for endpoint in \
    /healthz \
    /api/telephony/platform/health \
    /api/telephony/platform/anomalies \
    /api/telephony/platform/calls/summary \
    /api/telephony/platform/interconnects/summary; do
    safe_name=$(printf '%s' "$endpoint" | sed 's#^/##; s#[^A-Za-z0-9]#-#g')
    curl -fsS --max-time 5 "$ANALYTICS_URL$endpoint" >"$EVIDENCE_DIR/$safe_name.json"
    python3 -m json.tool "$EVIDENCE_DIR/$safe_name.json" >/dev/null
done

post_code=$(curl -sS --max-time 5 -o "$EVIDENCE_DIR/analytics-post-response.json" -w '%{http_code}' -X POST "$ANALYTICS_URL/api/telephony/platform/anomalies" || true)
printf '%s\n' "$post_code" | tee "$EVIDENCE_DIR/analytics-post-status.txt"
[ "$post_code" = "405" ]

echo
echo "=== READ-ONLY LIVE ACCEPTANCE ==="
ACCEPTANCE_TS=$(date -u +%Y%m%dT%H%M%SZ)
ACCEPTANCE_EVID="/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-live-acceptance/$ACCEPTANCE_TS"
bash "$REPO_ROOT/tools/telephony/telephony_anomaly_api_panel_live_acceptance_audit.sh" \
    --repo-root "$REPO_ROOT" \
    --evidence-dir "$ACCEPTANCE_EVID"
printf '%s\n' "$ACCEPTANCE_EVID" | tee "$EVIDENCE_DIR/live-acceptance-evidence.txt"

echo
echo "=== FINAL REPOSITORY AND INDEX VERIFICATION ==="
[ ! -e "$REPO_ROOT/.git/index.lock" ]
[ "$(stat -c '%U' "$REPO_ROOT/.git/index")" = "$REPO_OWNER" ]
[ "$(stat -c '%G' "$REPO_ROOT/.git/index")" = "$REPO_GROUP" ]
git_repo status --porcelain >"$EVIDENCE_DIR/repository-status-after.txt"
[ ! -s "$EVIDENCE_DIR/repository-status-after.txt" ]
stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$REPO_ROOT/.git/index" | tee "$EVIDENCE_DIR/index-after.txt"

find "$EVIDENCE_DIR" -maxdepth 1 -type f ! -name evidence-files.sha256 -print0 \
    | sort -z \
    | xargs -0 sha256sum >"$EVIDENCE_DIR/evidence-files.sha256"
sha256sum "$EVIDENCE_DIR/evidence-files.sha256" | tee "$EVIDENCE_DIR/evidence-manifest.sha256"

mutation_started=0
trap - ERR

echo
echo "=== DEPLOYMENT DECISION ==="
echo "deployment_status=passed"
echo "analytics_runtime_source=canonical-main"
echo "analytics_service_restart=completed"
echo "console_service_restart=none"
echo "console_static_assets=served-from-canonical-main"
echo "listener_scope=loopback-only"
echo "api_mode=read-only"
echo "notification_dispatch=none"
echo "traffic_enforcement=none"
echo "route_change=none"
echo "call_origination=none"
echo "dtmf_transmission=none"
echo "rollback_required=no"
echo "deployment_evidence=$EVIDENCE_DIR"
echo "live_acceptance_evidence=$ACCEPTANCE_EVID"
