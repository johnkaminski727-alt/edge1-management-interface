#!/bin/sh
set -eu

MODE=dry-run
START=0
EXPECTED_COMMIT=
for arg in "$@"; do
    case "$arg" in
        --dry-run) MODE=dry-run ;;
        --apply) MODE=apply ;;
        --start) START=1 ;;
        --expected-commit=*) EXPECTED_COMMIT=${arg#*=} ;;
        *) echo "usage: $0 [--dry-run|--apply] [--start] [--expected-commit=SHA]" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
repo_git() { git -c safe.directory="$REPO_ROOT" -C "$REPO_ROOT" "$@"; }
SERVICE=wwcx-ava-office.service
UNIT_SOURCE="$REPO_ROOT/deploy/systemd/$SERVICE"
UNIT_TARGET="/etc/systemd/system/$SERVICE"
DATA_DIR=/var/lib/wwcx-ava-office-manager
DATABASE="$DATA_DIR/office-manager.sqlite3"
RUNTIME_ROOT=/opt/wwcx-ava-office
RELEASES="$RUNTIME_ROOT/releases"
CURRENT="$RUNTIME_ROOT/current"
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/ava-office

python3 -m py_compile "$REPO_ROOT/server/ava_office_manager.py" "$REPO_ROOT/server/ava_office_manager_server.py"
HEAD=$(repo_git rev-parse HEAD 2>/dev/null || printf unknown)
BRANCH=$(repo_git branch --show-current 2>/dev/null || true)
DIRTY=$(repo_git status --porcelain 2>/dev/null || printf unknown)

echo "Ava Office read-only commissioning preflight"
echo "  mode: $MODE"
echo "  repository: $REPO_ROOT"
echo "  branch: ${BRANCH:-detached}"
echo "  commit: $HEAD"
echo "  start requested: $START"

if [ "$MODE" != apply ]; then
    echo "Dry run only. No files or services changed."
    exit 0
fi
if [ "$(id -u)" -ne 0 ]; then
    echo "--apply requires root" >&2
    exit 3
fi
if [ -z "$EXPECTED_COMMIT" ]; then
    echo "--apply requires --expected-commit=SHA" >&2
    exit 4
fi
case "$EXPECTED_COMMIT" in
    *[!0-9a-f]*|'') echo "expected commit must be lowercase hexadecimal" >&2; exit 4 ;;
esac
if [ ${#EXPECTED_COMMIT} -ne 40 ] || [ "$HEAD" != "$EXPECTED_COMMIT" ]; then
    echo "expected commit mismatch" >&2
    exit 4
fi
if [ -n "$DIRTY" ]; then
    echo "apply requires a clean checkout" >&2
    exit 4
fi
if [ -n "$BRANCH" ] && [ "$BRANCH" != main ]; then
    echo "apply requires main or a detached exact-commit checkout" >&2
    exit 4
fi
if [ ! -f "$UNIT_SOURCE" ]; then
    echo "missing service unit: $UNIT_SOURCE" >&2
    exit 4
fi

RELEASE="$RELEASES/$HEAD"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$EVIDENCE_ROOT/$STAMP"
install -d -m 0700 "$EVIDENCE"
printf '%s\n' "$HEAD" > "$EVIDENCE/repository-commit.txt"

WAS_ENABLED=0
WAS_ACTIVE=0
HAD_UNIT=0
CREATED_DB=0
CREATED_RELEASE=0
PREVIOUS_RUNTIME=
systemctl is-enabled --quiet "$SERVICE" 2>/dev/null && WAS_ENABLED=1 || true
systemctl is-active --quiet "$SERVICE" 2>/dev/null && WAS_ACTIVE=1 || true
[ -f "$UNIT_TARGET" ] && { HAD_UNIT=1; cp -a "$UNIT_TARGET" "$EVIDENCE/unit.before"; }
if [ -L "$CURRENT" ]; then PREVIOUS_RUNTIME=$(readlink -f "$CURRENT" || true); fi
printf '%s\n' "$PREVIOUS_RUNTIME" > "$EVIDENCE/runtime.before"

rollback() {
    rc=$?
    trap - EXIT INT TERM
    echo "Ava Office commissioning failed; restoring prior service state." >&2
    if [ -n "$PREVIOUS_RUNTIME" ] && [ -d "$PREVIOUS_RUNTIME" ]; then
        ln -sfn "$PREVIOUS_RUNTIME" "$CURRENT.rollback"
        mv -Tf "$CURRENT.rollback" "$CURRENT"
    else
        rm -f "$CURRENT"
    fi
    if [ "$HAD_UNIT" -eq 1 ]; then cp -a "$EVIDENCE/unit.before" "$UNIT_TARGET"; else rm -f "$UNIT_TARGET"; fi
    systemctl daemon-reload || true
    if [ "$WAS_ENABLED" -eq 1 ]; then systemctl enable "$SERVICE" >/dev/null 2>&1 || true; else systemctl disable "$SERVICE" >/dev/null 2>&1 || true; fi
    if [ "$WAS_ACTIVE" -eq 1 ]; then systemctl restart "$SERVICE" >/dev/null 2>&1 || true; else systemctl stop "$SERVICE" >/dev/null 2>&1 || true; fi
    if [ "$CREATED_DB" -eq 1 ]; then rm -f "$DATABASE" "$DATABASE-wal" "$DATABASE-shm"; fi
    if [ "$CREATED_RELEASE" -eq 1 ]; then rm -rf "$RELEASE"; fi
    exit "$rc"
}
trap rollback EXIT INT TERM

install -d -m 0755 -o root -g root "$RUNTIME_ROOT" "$RELEASES"
if [ ! -d "$RELEASE" ]; then
    install -d -m 0755 -o root -g root "$RELEASE"
    CREATED_RELEASE=1
fi
install -m 0555 -o root -g root "$REPO_ROOT/server/ava_office_manager_server.py" "$RELEASE/ava_office_manager_server.py"
install -m 0444 -o root -g root "$REPO_ROOT/server/ava_office_manager.py" "$RELEASE/ava_office_manager.py"
cmp -s "$REPO_ROOT/server/ava_office_manager_server.py" "$RELEASE/ava_office_manager_server.py"
cmp -s "$REPO_ROOT/server/ava_office_manager.py" "$RELEASE/ava_office_manager.py"
ln -sfn "$RELEASE" "$CURRENT.new"
mv -Tf "$CURRENT.new" "$CURRENT"
[ "$(readlink -f "$CURRENT")" = "$RELEASE" ]

install -d -m 0750 -o wwadmin -g wwadmin "$DATA_DIR"
if [ ! -f "$DATABASE" ]; then
    python3 - "$REPO_ROOT" "$DATABASE" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from server.ava_office_manager import OfficeManagerStore
store = OfficeManagerStore(sys.argv[2])
assert store.summary()["audit_chain_valid"] is True
PY
    chown wwadmin:wwadmin "$DATABASE"
    chmod 0600 "$DATABASE"
    CREATED_DB=1
fi

install -m 0644 -o root -g root "$UNIT_SOURCE" "$UNIT_TARGET"
systemctl daemon-reload
systemd-analyze verify "$UNIT_TARGET" 2> "$EVIDENCE/systemd-verify.txt"

if [ "$START" -eq 1 ]; then
    systemctl enable "$SERVICE" >/dev/null
    if [ "$WAS_ACTIVE" -eq 1 ]; then systemctl restart "$SERVICE"; else systemctl start "$SERVICE"; fi
    systemctl is-active --quiet "$SERVICE"
    python3 - <<'PY' > "$EVIDENCE/health.json"
import json, time, urllib.request
url = 'http://127.0.0.1:8116/healthz'
last = None
for _ in range(20):
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            payload = json.load(response)
        if response.status == 200 and payload.get('status') == 'ok' and payload.get('mode') == 'read-only':
            print(json.dumps(payload, sort_keys=True))
            raise SystemExit(0)
        last = payload
    except Exception as exc:
        last = str(exc)
    time.sleep(0.25)
raise SystemExit('Ava Office health check failed: %r' % (last,))
PY
    ss -ltn | grep -Eq '127\.0\.0\.1:8116[[:space:]]' || { echo "loopback listener 8116 not found" >&2; exit 5; }
    systemctl status "$SERVICE" --no-pager > "$EVIDENCE/service-status.txt"
else
    echo "Installed but not started; activation remains explicit." > "$EVIDENCE/service-status.txt"
fi

printf '%s\n' "$(readlink -f "$CURRENT")" > "$EVIDENCE/runtime.after"
sha256sum "$UNIT_TARGET" "$DATABASE" "$RELEASE/ava_office_manager_server.py" "$RELEASE/ava_office_manager.py" > "$EVIDENCE/installed-files.sha256"
trap - EXIT INT TERM
echo "Ava Office commissioning completed. Runtime: $RELEASE"
echo "Evidence: $EVIDENCE"
