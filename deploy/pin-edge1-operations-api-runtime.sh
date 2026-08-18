#!/bin/sh
set -eu

SERVICE=edge1-operations-api.service
DROPIN_DIR=/etc/systemd/system/edge1-operations-api.service.d
DROPIN=$DROPIN_DIR/20-immutable-runtime.conf
EVID_ROOT=/var/lib/wwcx-deployment-evidence/operations-api-runtime
MODE=dry-run
RUNTIME=

usage() {
    echo "usage: $0 --runtime /opt/edge1-operations-api-runtimes/<revision> [--apply]" >&2
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
    /opt/edge1-operations-api-runtimes/*) ;;
    *) echo "refusing runtime outside /opt/edge1-operations-api-runtimes" >&2; exit 3 ;;
esac

[ -d "$RUNTIME" ] || { echo "runtime does not exist: $RUNTIME" >&2; exit 4; }
[ -e "$RUNTIME/.git" ] || { echo "runtime is not a Git worktree: $RUNTIME" >&2; exit 5; }
[ -f "$RUNTIME/server/edge1_operations_api.py" ] || { echo "operations API source missing" >&2; exit 6; }
[ -f "$RUNTIME/config/edge1-operations-allowlist.json" ] || { echo "operations allowlist missing" >&2; exit 7; }

REVISION=$(git -C "$RUNTIME" rev-parse HEAD)
[ -z "$(git -C "$RUNTIME" status --porcelain)" ] || { echo "runtime worktree is not clean" >&2; exit 8; }

python3 -m py_compile "$RUNTIME/server/edge1_operations_api.py"
python3 -m json.tool "$RUNTIME/config/edge1-operations-allowlist.json" >/dev/null

if [ "$MODE" = dry-run ]; then
    echo "Dry run passed. runtime=$RUNTIME revision=$REVISION"
    echo "Use --apply to pin $SERVICE to this immutable runtime."
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
    if curl -fsS --max-time 2 http://127.0.0.1:8097/healthz >/dev/null 2>&1; then
        echo "Operations API runtime rollback complete and healthy."
        exit 0
    fi
    i=\$((i + 1))
    sleep 1
done
systemctl --no-pager --full status $SERVICE >&2 || true
exit 1
EOF
chmod 0700 "$EVID/rollback.sh"

install -d -o root -g root -m 0755 "$DROPIN_DIR"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT HUP INT TERM
cat > "$TMP" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/python3 $RUNTIME/server/edge1_operations_api.py
WorkingDirectory=$RUNTIME
Environment=EDGE1_OPS_ROOT=$RUNTIME
ReadOnlyPaths=$RUNTIME
EOF
install -o root -g root -m 0644 "$TMP" "$DROPIN"
rm -f "$TMP"
trap - EXIT HUP INT TERM

systemctl daemon-reload
systemd-analyze verify "$SERVICE"

if ! systemctl restart "$SERVICE"; then
    "$EVID/rollback.sh"
    exit 20
fi

HEALTH=$EVID/health.json
READY=0
i=1
while [ "$i" -le 20 ]; do
    if curl -fsS --max-time 2 http://127.0.0.1:8097/healthz > "$HEALTH" 2>/dev/null; then
        READY=1
        break
    fi
    sleep 1
    i=$((i + 1))
done

if [ "$READY" -ne 1 ]; then
    systemctl --no-pager --full status "$SERVICE" > "$EVID/status.failed.txt" 2>&1 || true
    journalctl -u "$SERVICE" --since '-2 minutes' --no-pager > "$EVID/journal.failed.txt" 2>&1 || true
    "$EVID/rollback.sh"
    exit 21
fi

python3 - "$HEALTH" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
if data.get("status") != "ok":
    raise SystemExit("health status is not ok")
if data.get("mutations_enabled") is not False:
    raise SystemExit("mutations unexpectedly enabled")
if not isinstance(data.get("actions"), int) or data["actions"] < 1:
    raise SystemExit("invalid action count")
PY

PID=$(systemctl show -p MainPID --value "$SERVICE")
[ "$PID" -gt 0 ] || { "$EVID/rollback.sh"; exit 22; }
CWD=$(readlink "/proc/$PID/cwd")
[ "$CWD" = "$RUNTIME" ] || { "$EVID/rollback.sh"; exit 23; }

systemctl show -p ExecStart --value "$SERVICE" | grep -F "$RUNTIME/server/edge1_operations_api.py" >/dev/null
systemctl show -p Environment --value "$SERVICE" | tr ' ' '\n' | grep -F "EDGE1_OPS_ROOT=$RUNTIME" >/dev/null
systemctl show -p NoNewPrivileges --value "$SERVICE" | grep -Fx yes >/dev/null
ss -lnt | grep -F '127.0.0.1:8097' >/dev/null
! ss -lnt | grep -E '0\.0\.0\.0:8097|\[::\]:8097' >/dev/null

systemctl cat "$SERVICE" > "$EVID/service.after.txt"
{
    echo "runtime=$RUNTIME"
    echo "revision=$REVISION"
    echo "pid=$PID"
    echo "process_cwd=$CWD"
    echo "readiness_attempt=$i"
} > "$EVID/acceptance.txt"
sha256sum \
    "$RUNTIME/server/edge1_operations_api.py" \
    "$RUNTIME/config/edge1-operations-allowlist.json" \
    "$RUNTIME/server/control_surface_diagnostics.py" \
    "$DROPIN" > "$EVID/SHA256SUMS"
chmod 0600 "$EVID/acceptance.txt" "$EVID/SHA256SUMS" "$HEALTH"

echo "Immutable Operations API runtime accepted."
echo "runtime=$RUNTIME"
echo "revision=$REVISION"
echo "evidence=$EVID"
echo "rollback=$EVID/rollback.sh"
