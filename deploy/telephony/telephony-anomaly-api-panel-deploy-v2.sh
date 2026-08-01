#!/bin/bash
set -Eeuo pipefail
umask 077

EXPECTED_HOST="edge1.ww.cx"
REPO_ROOT="/opt/edge1-management-interface"
CONSOLE_SERVICE="wwcx-telephony-console.service"
CONSOLE_URL="http://127.0.0.1:8096"
EVIDENCE_DIR=""
REQUIRED_COMMIT=""

usage() {
    cat <<'EOF'
Usage: sudo deploy/telephony/telephony-anomaly-api-panel-deploy-v2.sh \
  --required-commit SHA \
  --evidence-dir /var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/TIMESTAMP

Refreshes the canonical telephony console process so its in-memory route map
matches the repository, verifies the same-origin analytics proxy, and then
runs the rollback-capable analytics deployment.
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
    *[!0-9a-f]*|'') echo "ERROR required commit must be lowercase hexadecimal" >&2; exit 2 ;;
esac
case "$EVIDENCE_DIR" in
    /var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/*) ;;
    *) echo "ERROR evidence directory is outside the protected deployment root" >&2; exit 2 ;;
esac

for command in bash cat curl date find git grep hostname id install python3 runuser sha256sum sleep sort ss stat systemctl tee xargs; do
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
CONSOLE_EVID="$EVIDENCE_DIR/console-refresh"
ANALYTICS_EVID="$EVIDENCE_DIR/analytics-deployment"
ANALYTICS_DEPLOY="$REPO_ROOT/deploy/telephony/telephony-anomaly-api-panel-deploy.sh"

install -d -m 0700 "$EVIDENCE_DIR" "$CONSOLE_EVID"

console_refresh_started=0
console_refresh_complete=0
recovery_attempted=0

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

git_repo() {
    if [ "$REPO_OWNER" = "root" ]; then
        git -C "$REPO_ROOT" "$@"
    else
        runuser -u "$REPO_OWNER" -- env GIT_OPTIONAL_LOCKS=0 git -C "$REPO_ROOT" "$@"
    fi
}

recover_console() {
    original_rc=$?
    trap - ERR
    if [ "$console_refresh_started" -eq 1 ] && [ "$recovery_attempted" -eq 0 ]; then
        recovery_attempted=1
        echo
        echo "=== CONSOLE RECOVERY ==="
        systemctl restart "$CONSOLE_SERVICE" || true
        if wait_for_url "$CONSOLE_URL/healthz" 15; then
            echo "console_recovery_health=passed"
        else
            echo "console_recovery_health=failed"
        fi
        systemctl show "$CONSOLE_SERVICE" \
            --property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory,FragmentPath \
            >"$CONSOLE_EVID/console-service-after-recovery.txt" 2>&1 || true
        cat "$CONSOLE_EVID/console-service-after-recovery.txt" || true
        echo "console_recovery_attempted=yes"
    fi
    exit "$original_rc"
}
trap recover_console ERR

printf 'WW.CX TELEPHONY ANOMALY API/PANEL DEPLOYMENT V2\n'
printf 'Host: %s\n' "$HOST"
printf 'Time: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'Repository: %s\n' "$REPO_ROOT"
printf 'Required commit: %s\n' "$REQUIRED_COMMIT"
printf 'Evidence directory: %s\n' "$EVIDENCE_DIR"
printf 'Mutation boundary: one console restart, then the existing rollback-capable analytics deployment\n'

echo
echo "=== REPOSITORY PREFLIGHT ==="
[ -f "$REPO_ROOT/.git/index" ]
[ ! -e "$REPO_ROOT/.git/index.lock" ]
[ "$(stat -c '%U' "$REPO_ROOT/.git/index")" = "$REPO_OWNER" ]
[ "$(stat -c '%G' "$REPO_ROOT/.git/index")" = "$REPO_GROUP" ]
git_repo branch --show-current | tee "$EVIDENCE_DIR/repository-branch.txt"
[ "$(cat "$EVIDENCE_DIR/repository-branch.txt")" = "main" ]
git_repo status --porcelain >"$EVIDENCE_DIR/repository-status-before.txt"
[ ! -s "$EVIDENCE_DIR/repository-status-before.txt" ]
git_repo rev-parse HEAD | tee "$EVIDENCE_DIR/repository-head.txt"
git_repo cat-file -e "$REQUIRED_COMMIT^{commit}"
git_repo merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD
[ -f "$ANALYTICS_DEPLOY" ]
[ -f "$REPO_ROOT/server/telephony_status_server.py" ]

echo
echo "=== CONSOLE BASELINE ==="
systemctl is-active "$CONSOLE_SERVICE" | tee "$CONSOLE_EVID/console-active-before.txt"
systemctl show "$CONSOLE_SERVICE" \
    --property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory,FragmentPath,User,Group \
    | tee "$CONSOLE_EVID/console-service-before.txt"
grep -Fq "$REPO_ROOT/server/telephony_status_server.py" "$CONSOLE_EVID/console-service-before.txt"
CONSOLE_PID_BEFORE=$(systemctl show "$CONSOLE_SERVICE" --property=MainPID --value)
[ "$CONSOLE_PID_BEFORE" -gt 0 ]
ss -lntp >"$CONSOLE_EVID/listeners-before.txt"
grep -E '127\.0\.0\.1:8096|\[::1\]:8096' "$CONSOLE_EVID/listeners-before.txt" >/dev/null
if grep -E '0\.0\.0\.0:8096|\[::\]:8096|\*:8096' "$CONSOLE_EVID/listeners-before.txt" >/dev/null; then
    echo "ERROR unsafe console listener detected" >&2
    false
fi
curl -fsS --max-time 5 "$CONSOLE_URL/healthz" >"$CONSOLE_EVID/healthz-before.json"
BEFORE_PROXY_CODE=$(curl -sS --max-time 5 -o "$CONSOLE_EVID/analytics-health-before.json" -w '%{http_code}' "$CONSOLE_URL/api/telephony/analytics/health" || true)
printf '%s\n' "$BEFORE_PROXY_CODE" | tee "$CONSOLE_EVID/analytics-health-before.http-status.txt"

echo
echo "=== CANONICAL CONSOLE PROCESS REFRESH ==="
console_refresh_started=1
systemctl restart "$CONSOLE_SERVICE"
wait_for_url "$CONSOLE_URL/healthz" 15
systemctl is-active "$CONSOLE_SERVICE" | tee "$CONSOLE_EVID/console-active-after.txt"
systemctl show "$CONSOLE_SERVICE" \
    --property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory,FragmentPath,User,Group \
    | tee "$CONSOLE_EVID/console-service-after.txt"
grep -Fq "$REPO_ROOT/server/telephony_status_server.py" "$CONSOLE_EVID/console-service-after.txt"
CONSOLE_PID_AFTER=$(systemctl show "$CONSOLE_SERVICE" --property=MainPID --value)
[ "$CONSOLE_PID_AFTER" -gt 0 ]
[ "$CONSOLE_PID_AFTER" != "$CONSOLE_PID_BEFORE" ]

ss -lntp >"$CONSOLE_EVID/listeners-after.txt"
grep -E '127\.0\.0\.1:8096|\[::1\]:8096' "$CONSOLE_EVID/listeners-after.txt" >/dev/null
if grep -E '0\.0\.0\.0:8096|\[::\]:8096|\*:8096' "$CONSOLE_EVID/listeners-after.txt" >/dev/null; then
    echo "ERROR unsafe console listener detected after restart" >&2
    false
fi

PROXY_CODE=$(curl -sS --max-time 5 -o "$CONSOLE_EVID/analytics-health-after.json" -w '%{http_code}' "$CONSOLE_URL/api/telephony/analytics/health" || true)
printf '%s\n' "$PROXY_CODE" | tee "$CONSOLE_EVID/analytics-health-after.http-status.txt"
[ "$PROXY_CODE" = "200" ]
python3 -m json.tool "$CONSOLE_EVID/analytics-health-after.json" >/dev/null
curl -fsS --max-time 5 "$CONSOLE_URL/" >"$CONSOLE_EVID/console-index-after.html"
grep -Fq 'telephony-anomalies.js' "$CONSOLE_EVID/console-index-after.html"
grep -Fq 'id="analytics-anomalies"' "$CONSOLE_EVID/console-index-after.html"
curl -fsS --max-time 5 "$CONSOLE_URL/telephony-anomalies.js" >"$CONSOLE_EVID/telephony-anomalies-after.js"
curl -fsS --max-time 5 "$CONSOLE_URL/telephony-anomalies.css" >"$CONSOLE_EVID/telephony-anomalies-after.css"
console_refresh_complete=1

echo
echo "=== DELEGATED ANALYTICS DEPLOYMENT ==="
echo "console_refresh=completed"
echo "analytics_deployment_engine=$ANALYTICS_DEPLOY"
bash "$ANALYTICS_DEPLOY" \
    --expected-host "$EXPECTED_HOST" \
    --repo-root "$REPO_ROOT" \
    --required-commit "$REQUIRED_COMMIT" \
    --evidence-dir "$ANALYTICS_EVID" 2>&1 | tee "$EVIDENCE_DIR/analytics-deployment.log"

echo
echo "=== FINAL CONSOLE VERIFICATION ==="
wait_for_url "$CONSOLE_URL/healthz" 15
FINAL_PROXY_CODE=$(curl -sS --max-time 5 -o "$CONSOLE_EVID/analytics-health-final.json" -w '%{http_code}' "$CONSOLE_URL/api/telephony/analytics/health" || true)
printf '%s\n' "$FINAL_PROXY_CODE" | tee "$CONSOLE_EVID/analytics-health-final.http-status.txt"
[ "$FINAL_PROXY_CODE" = "200" ]
python3 -m json.tool "$CONSOLE_EVID/analytics-health-final.json" >/dev/null
systemctl show "$CONSOLE_SERVICE" \
    --property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory,FragmentPath,User,Group \
    | tee "$CONSOLE_EVID/console-service-final.txt"

echo
echo "=== FINAL REPOSITORY SAFETY ==="
[ ! -e "$REPO_ROOT/.git/index.lock" ]
[ "$(stat -c '%U' "$REPO_ROOT/.git/index")" = "$REPO_OWNER" ]
[ "$(stat -c '%G' "$REPO_ROOT/.git/index")" = "$REPO_GROUP" ]
git_repo status --porcelain >"$EVIDENCE_DIR/repository-status-after.txt"
[ ! -s "$EVIDENCE_DIR/repository-status-after.txt" ]
stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$REPO_ROOT/.git/index" | tee "$EVIDENCE_DIR/index-after.txt"

find "$EVIDENCE_DIR" -type f \
    ! -path "$EVIDENCE_DIR/evidence-files.sha256" \
    ! -path "$EVIDENCE_DIR/evidence-manifest.sha256" -print0 \
    | sort -z \
    | xargs -0 sha256sum >"$EVIDENCE_DIR/evidence-files.sha256"
sha256sum "$EVIDENCE_DIR/evidence-files.sha256" | tee "$EVIDENCE_DIR/evidence-manifest.sha256"

trap - ERR

echo
echo "=== V2 DEPLOYMENT DECISION ==="
echo "deployment_status=passed"
echo "console_service_restart=completed"
echo "console_runtime_source=canonical-main"
echo "console_proxy_route=passed"
echo "analytics_deployment=passed"
echo "analytics_rollback_required=no"
echo "listener_scope=loopback-only"
echo "call_origination=none"
echo "dtmf_transmission=none"
echo "route_change=none"
echo "notification_dispatch=none"
echo "traffic_enforcement=none"
echo "deployment_evidence=$EVIDENCE_DIR"
echo "console_evidence=$CONSOLE_EVID"
echo "analytics_evidence=$ANALYTICS_EVID"
