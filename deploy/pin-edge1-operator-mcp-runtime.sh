#!/bin/sh
set -eu

SERVICE=edge1-operator-mcp.service
DROPIN_DIR=/etc/systemd/system/edge1-operator-mcp.service.d
DROPIN=$DROPIN_DIR/20-immutable-runtime.conf
EVID_ROOT=/var/lib/wwcx-deployment-evidence/operator-mcp-runtime
MODE=dry-run
RUNTIME=
READ_SCOPES=edge1.status.read,edge1.telephony.read,edge1.messaging.read

usage() {
    echo "usage: $0 --runtime /opt/edge1-operator-mcp-runtimes/<revision> [--apply]" >&2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --runtime)
            [ "$#" -ge 2 ] || { usage; exit 2; }
            RUNTIME=$2
            shift 2
            ;;
        --apply)
            MODE=apply
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

[ -n "$RUNTIME" ] || { echo "--runtime is required" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run with sudo/root after the runtime worktree is prepared by wwadmin" >&2; exit 1; }
case "$RUNTIME" in
    /opt/edge1-operator-mcp-runtimes/*) ;;
    *) echo "refusing runtime outside /opt/edge1-operator-mcp-runtimes" >&2; exit 3 ;;
esac

[ -d "$RUNTIME" ] || { echo "runtime does not exist: $RUNTIME" >&2; exit 4; }
[ -e "$RUNTIME/.git" ] || { echo "runtime is not a Git worktree: $RUNTIME" >&2; exit 5; }
for rel in \
    server/edge1_operator_http.py \
    server/edge1_operator_entrypoint.py \
    server/edge1_operator_mcp_protocol.py \
    server/edge1_operator_mcp_adapter.py \
    server/edge1_operator_runtime.py \
    server/edge1_operator_capabilities.py \
    server/edge1_operator_operations_client.py \
    config/edge1-operator-capabilities.json
 do
    [ -f "$RUNTIME/$rel" ] || { echo "required Operator runtime asset missing: $rel" >&2; exit 6; }
 done

REVISION=$(git -C "$RUNTIME" rev-parse HEAD)
[ -z "$(git -C "$RUNTIME" status --porcelain)" ] || { echo "runtime worktree is not clean" >&2; exit 7; }
python3 -m py_compile \
    "$RUNTIME/server/edge1_operator_http.py" \
    "$RUNTIME/server/edge1_operator_entrypoint.py" \
    "$RUNTIME/server/edge1_operator_mcp_protocol.py" \
    "$RUNTIME/server/edge1_operator_mcp_adapter.py" \
    "$RUNTIME/server/edge1_operator_runtime.py" \
    "$RUNTIME/server/edge1_operator_capabilities.py" \
    "$RUNTIME/server/edge1_operator_operations_client.py"
python3 -m json.tool "$RUNTIME/config/edge1-operator-capabilities.json" >/dev/null

if [ "$MODE" = dry-run ]; then
    echo "Operator MCP runtime dry run passed. runtime=$RUNTIME revision=$REVISION"
    echo "Read-only scopes will be fixed in ExecStart: $READ_SCOPES"
    exit 0
fi

systemctl cat "$SERVICE" >/dev/null
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVID=$EVID_ROOT/$STAMP
install -d -o root -g root -m 0700 "$EVID"
systemctl cat "$SERVICE" > "$EVID/service.before.txt"
HAD_DROPIN=0
if [ -e "$DROPIN" ]; then
    HAD_DROPIN=1
    cp -a "$DROPIN" "$EVID/20-immutable-runtime.conf.before"
fi
if [ "$HAD_DROPIN" -eq 1 ]; then
    RESTORE="cp -a '$EVID/20-immutable-runtime.conf.before' '$DROPIN'"
else
    RESTORE="rm -f '$DROPIN'"
fi
cat > "$EVID/rollback.sh" <<EOF
#!/bin/sh
set -eu
$RESTORE
systemctl daemon-reload
systemctl restart $SERVICE
i=0
while [ "\$i" -lt 20 ]; do
    code=\$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:8102/mcp 2>/dev/null || true)
    if [ "\$code" = 401 ]; then
        echo "Operator MCP runtime rollback complete and listening."
        exit 0
    fi
    i=\$((i + 1))
    sleep 1
done
systemctl --no-pager --full status $SERVICE >&2 || true
exit 1
EOF
chmod 0700 "$EVID/rollback.sh"

capture_failure_evidence() {
    reason=$1
    {
        echo "runtime=$RUNTIME"
        echo "revision=$REVISION"
        echo "reason=$reason"
        echo "read_scopes=$READ_SCOPES"
    } > "$EVID/failure.txt"
    systemctl show "$SERVICE" \
        -p Id -p LoadState -p ActiveState -p SubState -p MainPID \
        -p WorkingDirectory -p NoNewPrivileges -p ExecStart \
        > "$EVID/service.failure.txt" 2>&1 || true
    journalctl -u "$SERVICE" --since '-3 minutes' --no-pager -n 160 \
        > "$EVID/journal.failure.txt" 2>&1 || true
    chmod 0600 "$EVID/failure.txt" "$EVID/service.failure.txt" "$EVID/journal.failure.txt" 2>/dev/null || true
}

fail_after_apply() {
    code=$1
    reason=$2
    capture_failure_evidence "$reason"
    echo "ERROR: Operator MCP runtime pin failed: $reason" >&2
    echo "failure_evidence=$EVID" >&2
    "$EVID/rollback.sh" || true
    exit "$code"
}

install -d -o root -g root -m 0755 "$DROPIN_DIR"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT HUP INT TERM
cat > "$TMP" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/env EDGE1_OPERATOR_CAPABILITIES=$RUNTIME/config/edge1-operator-capabilities.json EDGE1_OPERATOR_SCOPES=$READ_SCOPES /usr/bin/python3 -m server.edge1_operator_http --host 127.0.0.1 --port 8102
WorkingDirectory=$RUNTIME
ReadOnlyPaths=$RUNTIME
EOF
install -o root -g root -m 0644 "$TMP" "$DROPIN"
rm -f "$TMP"
trap - EXIT HUP INT TERM

systemctl daemon-reload
if ! systemd-analyze verify "$SERVICE" > "$EVID/systemd-verify.txt" 2>&1; then
    cat "$EVID/systemd-verify.txt" >&2
    fail_after_apply 19 "systemd unit verification failed"
fi
if ! systemctl restart "$SERVICE"; then
    fail_after_apply 20 "service restart failed"
fi

READY=0
i=1
while [ "$i" -le 20 ]; do
    code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:8102/mcp 2>/dev/null || true)
    if [ "$code" = 401 ]; then
        READY=1
        break
    fi
    sleep 1
    i=$((i + 1))
done
[ "$READY" -eq 1 ] || fail_after_apply 21 "loopback MCP readiness did not return HTTP 401"

PID=$(systemctl show -p MainPID --value "$SERVICE")
case "$PID" in
    ''|0|*[!0-9]*) fail_after_apply 22 "service MainPID is unavailable" ;;
esac
CWD=$(readlink "/proc/$PID/cwd" 2>/dev/null || true)
[ "$CWD" = "$RUNTIME" ] || fail_after_apply 23 "service working directory does not match immutable runtime"
if ! systemctl show -p ExecStart --value "$SERVICE" | grep -F -- '/usr/bin/env EDGE1_OPERATOR_CAPABILITIES=' >/dev/null; then
    fail_after_apply 24 "fixed ExecStart capability environment is absent"
fi
if ! systemctl show -p ExecStart --value "$SERVICE" | grep -F -- '-m server.edge1_operator_http' >/dev/null; then
    fail_after_apply 25 "Operator MCP module ExecStart is absent"
fi
if ! python3 - "$PID" "$RUNTIME" "$READ_SCOPES" <<'PY'
from pathlib import Path
import sys

pid, runtime, scopes = sys.argv[1:]
raw = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
env = {}
for item in raw:
    if b"=" not in item:
        continue
    key, value = item.split(b"=", 1)
    env[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
expected_capabilities = runtime + "/config/edge1-operator-capabilities.json"
if env.get("EDGE1_OPERATOR_CAPABILITIES") != expected_capabilities:
    raise SystemExit("effective capability manifest path mismatch")
if env.get("EDGE1_OPERATOR_SCOPES") != scopes:
    raise SystemExit("effective Operator scope set mismatch")
if "edge1.telephony.control.safe" in env.get("EDGE1_OPERATOR_SCOPES", ""):
    raise SystemExit("write scope unexpectedly present")
PY
then
    fail_after_apply 26 "effective process capability environment failed verification"
fi
if ! systemctl show -p NoNewPrivileges --value "$SERVICE" | grep -Fx yes >/dev/null; then
    fail_after_apply 27 "NoNewPrivileges is not active"
fi
if ! ss -lnt | grep -F '127.0.0.1:8102' >/dev/null; then
    fail_after_apply 28 "loopback MCP listener is absent"
fi
if ss -lnt | grep -E '0\.0\.0\.0:8102|\[::\]:8102' >/dev/null; then
    fail_after_apply 29 "MCP listener is exposed outside loopback"
fi

systemctl cat "$SERVICE" > "$EVID/service.after.txt"
{
    echo "runtime=$RUNTIME"
    echo "revision=$REVISION"
    echo "pid=$PID"
    echo "process_cwd=$CWD"
    echo "readiness_attempt=$i"
    echo "operator_scopes=$READ_SCOPES"
    echo "capability_environment_source=fixed_execstart"
    echo "telephony_safe_control_scope_present=false"
} > "$EVID/acceptance.txt"
sha256sum \
    "$RUNTIME/server/edge1_operator_http.py" \
    "$RUNTIME/server/edge1_operator_entrypoint.py" \
    "$RUNTIME/server/edge1_operator_mcp_protocol.py" \
    "$RUNTIME/server/edge1_operator_mcp_adapter.py" \
    "$RUNTIME/server/edge1_operator_runtime.py" \
    "$RUNTIME/server/edge1_operator_capabilities.py" \
    "$RUNTIME/server/edge1_operator_operations_client.py" \
    "$RUNTIME/config/edge1-operator-capabilities.json" \
    "$DROPIN" > "$EVID/SHA256SUMS"
chmod 0600 "$EVID/acceptance.txt" "$EVID/SHA256SUMS" "$EVID/systemd-verify.txt"

echo "Immutable Operator MCP runtime accepted."
echo "runtime=$RUNTIME"
echo "revision=$REVISION"
echo "evidence=$EVID"
echo "rollback=$EVID/rollback.sh"
