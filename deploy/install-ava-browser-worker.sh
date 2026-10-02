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
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
repo_git() { git -c safe.directory="$REPO_ROOT" -C "$REPO_ROOT" "$@"; }

SERVICE=private-ai-browser-worker.service
UNIT_SOURCE="$REPO_ROOT/deploy/$SERVICE"
UNIT_TARGET="/etc/systemd/system/$SERVICE"
RUNTIME_ROOT=/opt/wwcx-private-ai-browser-worker
RELEASES="$RUNTIME_ROOT/releases"
CURRENT="$RUNTIME_ROOT/current"
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/ava-browser-worker
GATEWAY_ENV=/etc/bigbird-ai-gateway.env
WORKER_ENV=/etc/wwcx/private-ai-browser-worker.env

for source in "$REPO_ROOT/server/private_ai_browser_worker.py" "$REPO_ROOT/server/ava_agent_controller.py" "$UNIT_SOURCE"; do
    [ -f "$source" ] || { echo "missing source: $source" >&2; exit 4; }
done
python3 -m py_compile "$REPO_ROOT/server/private_ai_browser_worker.py" "$REPO_ROOT/server/ava_agent_controller.py"

HEAD=$(repo_git rev-parse HEAD 2>/dev/null || printf unknown)
BRANCH=$(repo_git branch --show-current 2>/dev/null || true)
DIRTY=$(repo_git status --porcelain 2>/dev/null || printf unknown)

echo "Ava browser worker commissioning preflight"
echo "  mode: $MODE"
echo "  repository: $REPO_ROOT"
echo "  branch: ${BRANCH:-detached}"
echo "  commit: $HEAD"
echo "  start requested: $START"

if [ "$MODE" != apply ]; then
    echo "Dry run only. No files or services changed."
    exit 0
fi
[ "$(id -u)" -eq 0 ] || { echo "--apply requires root" >&2; exit 3; }
[ -n "$EXPECTED_COMMIT" ] || { echo "--apply requires --expected-commit=SHA" >&2; exit 4; }
case "$EXPECTED_COMMIT" in *[!0-9a-f]*|'') echo "expected commit must be lowercase hexadecimal" >&2; exit 4 ;; esac
[ ${#EXPECTED_COMMIT} -eq 40 ] && [ "$HEAD" = "$EXPECTED_COMMIT" ] || { echo "expected commit mismatch" >&2; exit 4; }
[ -z "$DIRTY" ] || { echo "apply requires a clean checkout" >&2; exit 4; }
if [ -n "$BRANCH" ] && [ "$BRANCH" != main ]; then
    echo "apply requires main or a detached exact-commit checkout" >&2
    exit 4
fi
[ -f "$GATEWAY_ENV" ] || { echo "Ava gateway environment is unavailable" >&2; exit 4; }
getent passwd bigbird-ai >/dev/null 2>&1 || { echo "bigbird-ai service account is unavailable" >&2; exit 4; }
grep -q '^BB_RELAY_KEY_ID=' "$GATEWAY_ENV" || { echo "gateway relay key id is not configured" >&2; exit 4; }
grep -q '^BB_RELAY_SECRET=' "$GATEWAY_ENV" || { echo "gateway relay secret is not configured" >&2; exit 4; }

QUEUE_ENV=
for candidate in "$WORKER_ENV" /etc/wwcx/bigbird-ai-poller.env /etc/bigbird-ai-poller.env; do
    [ -r "$candidate" ] || continue
    if grep -q '^BB_BROWSER_WORKER_KEY_ID=' "$candidate" && grep -q '^BB_BROWSER_WORKER_SECRET=' "$candidate"; then
        QUEUE_ENV="$candidate"
        break
    fi
done
[ -n "$QUEUE_ENV" ] || { echo "no reusable WW.CX queue worker identity is present; restore/rotate it before activation" >&2; exit 4; }

RELEASE="$RELEASES/$HEAD"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$EVIDENCE_ROOT/$STAMP"
install -d -m 0700 "$EVIDENCE"
printf '%s
' "$HEAD" > "$EVIDENCE/repository-commit.txt"

WAS_ENABLED=0
WAS_ACTIVE=0
HAD_UNIT=0
HAD_ENV=0
CREATED_RELEASE=0
PREVIOUS_RUNTIME=
systemctl is-enabled --quiet "$SERVICE" 2>/dev/null && WAS_ENABLED=1 || true
systemctl is-active --quiet "$SERVICE" 2>/dev/null && WAS_ACTIVE=1 || true
[ -f "$UNIT_TARGET" ] && { HAD_UNIT=1; cp -a "$UNIT_TARGET" "$EVIDENCE/unit.before"; }
[ -f "$WORKER_ENV" ] && { HAD_ENV=1; cp -a "$WORKER_ENV" "$EVIDENCE/env.before"; }
if [ -L "$CURRENT" ]; then PREVIOUS_RUNTIME=$(readlink -f "$CURRENT" || true); fi
printf '%s
' "$PREVIOUS_RUNTIME" > "$EVIDENCE/runtime.before"

rollback() {
    rc=$?
    trap - EXIT INT TERM
    [ -n "${TMP:-}" ] && rm -f "$TMP" || true
    echo "Ava browser worker commissioning failed; restoring prior service state." >&2
    if [ -n "$PREVIOUS_RUNTIME" ] && [ -d "$PREVIOUS_RUNTIME" ]; then
        ln -sfn "$PREVIOUS_RUNTIME" "$CURRENT.rollback"
        mv -Tf "$CURRENT.rollback" "$CURRENT"
    else
        rm -f "$CURRENT"
    fi
    if [ "$HAD_UNIT" -eq 1 ]; then cp -a "$EVIDENCE/unit.before" "$UNIT_TARGET"; else rm -f "$UNIT_TARGET"; fi
    if [ "$HAD_ENV" -eq 1 ]; then cp -a "$EVIDENCE/env.before" "$WORKER_ENV"; else rm -f "$WORKER_ENV"; fi
    systemctl daemon-reload || true
    if [ "$WAS_ENABLED" -eq 1 ]; then systemctl enable "$SERVICE" >/dev/null 2>&1 || true; else systemctl disable "$SERVICE" >/dev/null 2>&1 || true; fi
    if [ "$WAS_ACTIVE" -eq 1 ]; then systemctl restart "$SERVICE" >/dev/null 2>&1 || true; else systemctl stop "$SERVICE" >/dev/null 2>&1 || true; fi
    if [ "$CREATED_RELEASE" -eq 1 ]; then rm -rf "$RELEASE"; fi
    exit "$rc"
}
trap rollback EXIT INT TERM

install -d -m 0755 -o root -g root "$RUNTIME_ROOT" "$RELEASES"
if [ -e "$RELEASE" ]; then
    [ -d "$RELEASE" ] || { echo "release path is not a directory: $RELEASE" >&2; exit 4; }
    cmp -s "$REPO_ROOT/server/private_ai_browser_worker.py" "$RELEASE/private_ai_browser_worker.py"
    cmp -s "$REPO_ROOT/server/ava_agent_controller.py" "$RELEASE/ava_agent_controller.py"
else
    install -d -m 0755 -o root -g root "$RELEASE"
    CREATED_RELEASE=1
    install -m 0555 -o root -g root "$REPO_ROOT/server/private_ai_browser_worker.py" "$RELEASE/private_ai_browser_worker.py"
    install -m 0444 -o root -g root "$REPO_ROOT/server/ava_agent_controller.py" "$RELEASE/ava_agent_controller.py"
fi

ln -sfn "$RELEASE" "$CURRENT.new"
mv -Tf "$CURRENT.new" "$CURRENT"
[ "$(readlink -f "$CURRENT")" = "$RELEASE" ]

install -d -o root -g bigbird-ai -m 0750 /etc/wwcx
TMP=$(mktemp /etc/wwcx/.private-ai-browser-worker.env.XXXXXX)
{
    sed -n -E '/^BB_BROWSER_WORKER_(KEY_ID|SECRET)=/p' "$QUEUE_ENV"
    sed -n -E '/^BB_RELAY_(KEY_ID|SECRET)=/p' "$GATEWAY_ENV"
    printf '%s
'         'BB_BROWSER_QUEUE_URL=https://ww.cx/api/bigbird-ai-worker.php'         'BB_BROWSER_GATEWAY_URL=http://127.0.0.1:8787/v1/chat'         'BB_BROWSER_WORKER_ID=edge1-private-ai-browser'
} > "$TMP"
for key in BB_BROWSER_WORKER_KEY_ID BB_BROWSER_WORKER_SECRET BB_RELAY_KEY_ID BB_RELAY_SECRET BB_BROWSER_QUEUE_URL BB_BROWSER_GATEWAY_URL BB_BROWSER_WORKER_ID; do
    [ "$(grep -c "^$key=" "$TMP")" -eq 1 ] || { echo "worker environment has invalid $key cardinality" >&2; exit 4; }
done
chown root:bigbird-ai "$TMP"
chmod 0640 "$TMP"
mv -f "$TMP" "$WORKER_ENV"
trap rollback EXIT INT TERM

install -m 0644 -o root -g root "$UNIT_SOURCE" "$UNIT_TARGET"
systemctl daemon-reload
systemd-analyze verify "$UNIT_TARGET" 2> "$EVIDENCE/systemd-verify.txt"

if [ "$START" -eq 1 ]; then
    systemctl enable "$SERVICE" >/dev/null
    if [ "$WAS_ACTIVE" -eq 1 ]; then systemctl restart "$SERVICE"; else systemctl start "$SERVICE"; fi
    systemctl is-active --quiet "$SERVICE"
    systemctl status "$SERVICE" --no-pager > "$EVIDENCE/service-status.txt"
else
    echo "Installed but not started; activation remains explicit." > "$EVIDENCE/service-status.txt"
fi

printf '%s
' "$(readlink -f "$CURRENT")" > "$EVIDENCE/runtime.after"
sha256sum "$UNIT_TARGET" "$RELEASE/private_ai_browser_worker.py" "$RELEASE/ava_agent_controller.py" > "$EVIDENCE/installed-files.sha256"
trap - EXIT INT TERM
echo "Ava browser worker commissioning completed. Runtime: $RELEASE"
echo "Environment: $WORKER_ENV (secret values not displayed)"
echo "Evidence: $EVIDENCE"
