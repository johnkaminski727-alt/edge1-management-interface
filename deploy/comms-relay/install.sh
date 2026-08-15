#!/bin/sh
set -eu
MODE=dry-run
START=0
EXPECTED_COMMIT=
for arg in "$@"; do
    case "$arg" in
        --apply) MODE=apply ;;
        --start) START=1 ;;
        --dry-run) MODE=dry-run ;;
        --expected-commit=*) EXPECTED_COMMIT=${arg#*=} ;;
        *) echo "usage: $0 [--dry-run|--apply] [--start] [--expected-commit=SHA]" >&2; exit 2 ;;
    esac
done
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
UNIT_SOURCE="$SCRIPT_DIR/edge1-comms-relay.service"
CONFIG_SOURCE="$REPO_ROOT/config/comms-relay.example.json"
SMOKE="$SCRIPT_DIR/smoke-test.py"
UNIT_TARGET=/etc/systemd/system/edge1-comms-relay.service
CONFIG_TARGET=/etc/wwcx/comms-relay.json
DATA_DIR=/var/lib/wwcx-comms
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/comms-relay
SERVICE_USER=wwcx-comms
python3 "$REPO_ROOT/server/edge1_comms_cli.py" config validate "$CONFIG_SOURCE" >/dev/null
python3 -m py_compile "$REPO_ROOT/server/edge1_commsd.py" "$SMOKE"
HEAD=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)
BRANCH=$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || printf unknown)
DIRTY=$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null || printf unknown)
echo "Edge1 Comms Relay deployment preflight"
echo "  mode: $MODE"
echo "  repository: $REPO_ROOT"
echo "  branch: $BRANCH"
echo "  commit: $HEAD"
echo "  start requested: $START"
if [ -n "$EXPECTED_COMMIT" ] && [ "$HEAD" != "$EXPECTED_COMMIT" ]; then echo "expected commit mismatch" >&2; exit 4; fi
if [ "$MODE" != apply ]; then echo "Dry run only. No files or services changed."; exit 0; fi
if [ "$(id -u)" -ne 0 ]; then echo "--apply requires root" >&2; exit 3; fi
if [ "$BRANCH" != main ]; then echo "apply requires a main-branch checkout" >&2; exit 4; fi
if [ -n "$DIRTY" ]; then echo "apply requires a clean working tree" >&2; exit 4; fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$EVIDENCE_ROOT/$STAMP"
mkdir -p "$EVIDENCE"; chmod 0700 "$EVIDENCE"
printf '%s\n' "$HEAD" > "$EVIDENCE/repository-commit.txt"
WAS_ENABLED=0; WAS_ACTIVE=0; HAD_UNIT=0; HAD_CONFIG=0
systemctl is-enabled --quiet edge1-comms-relay.service 2>/dev/null && WAS_ENABLED=1 || true
systemctl is-active --quiet edge1-comms-relay.service 2>/dev/null && WAS_ACTIVE=1 || true
if [ "$WAS_ACTIVE" -eq 1 ] && [ "$START" -ne 1 ]; then echo "active service upgrade requires --start so the validated unit is restarted" >&2; exit 4; fi
[ -f "$UNIT_TARGET" ] && { HAD_UNIT=1; cp -a "$UNIT_TARGET" "$EVIDENCE/unit.before"; }
[ -f "$CONFIG_TARGET" ] && { HAD_CONFIG=1; cp -a "$CONFIG_TARGET" "$EVIDENCE/config.before"; }
rollback() {
    rc=$?
    trap - EXIT INT TERM
    echo "Deployment failed; restoring prior service state." >&2
    if [ "$HAD_UNIT" -eq 1 ]; then cp -a "$EVIDENCE/unit.before" "$UNIT_TARGET"; else rm -f "$UNIT_TARGET"; fi
    if [ "$HAD_CONFIG" -eq 1 ]; then cp -a "$EVIDENCE/config.before" "$CONFIG_TARGET"; else rm -f "$CONFIG_TARGET"; fi
    systemctl daemon-reload || true
    if [ "$WAS_ENABLED" -eq 1 ]; then systemctl enable edge1-comms-relay.service >/dev/null 2>&1 || true; else systemctl disable edge1-comms-relay.service >/dev/null 2>&1 || true; fi
    if [ "$WAS_ACTIVE" -eq 1 ]; then systemctl restart edge1-comms-relay.service || true; else systemctl stop edge1-comms-relay.service >/dev/null 2>&1 || true; fi
    exit "$rc"
}
trap rollback EXIT INT TERM
if ! getent group "$SERVICE_USER" >/dev/null 2>&1; then groupadd --system "$SERVICE_USER"; fi
if ! id "$SERVICE_USER" >/dev/null 2>&1; then useradd --system --gid "$SERVICE_USER" --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"; fi
install -d -m 0750 -o root -g "$SERVICE_USER" /etc/wwcx
install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR" "$DATA_DIR/config-control"
install -m 0644 -o root -g root "$UNIT_SOURCE" "$UNIT_TARGET"
if [ ! -f "$CONFIG_TARGET" ]; then install -m 0640 -o root -g "$SERVICE_USER" "$CONFIG_SOURCE" "$CONFIG_TARGET"; fi
python3 "$REPO_ROOT/server/edge1_comms_cli.py" config validate "$CONFIG_TARGET" > "$EVIDENCE/config-validation.json"
systemctl daemon-reload
systemd-analyze verify "$UNIT_TARGET" 2> "$EVIDENCE/systemd-verify.txt"
if [ "$START" -eq 1 ]; then
    systemctl enable edge1-comms-relay.service
    if [ "$WAS_ACTIVE" -eq 1 ]; then systemctl restart edge1-comms-relay.service; else systemctl start edge1-comms-relay.service; fi
    systemctl is-active --quiet edge1-comms-relay.service
    python3 "$SMOKE" --config "$CONFIG_TARGET" | tee "$EVIDENCE/smoke-test.txt"
    systemctl status edge1-comms-relay.service --no-pager > "$EVIDENCE/service-status.txt"
else
    echo "Installed but not started; activation remains explicit." > "$EVIDENCE/service-status.txt"
fi
sha256sum "$UNIT_TARGET" "$CONFIG_TARGET" > "$EVIDENCE/installed-files.sha256"
trap - EXIT INT TERM
echo "Deployment completed. Evidence: $EVIDENCE"
