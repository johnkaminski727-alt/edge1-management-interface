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

SERVICE=bigbird-ai-gateway.service
UNIT_SOURCE="$REPO_ROOT/deploy/systemd/$SERVICE"
UNIT_TARGET="/etc/systemd/system/$SERVICE"
RUNTIME_ROOT=/opt/bigbird-ai-gateway
RELEASES="$RUNTIME_ROOT/releases"
CURRENT="$RUNTIME_ROOT/current"
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/ava-gateway
ENV_FILE=/etc/bigbird-ai-gateway.env

for source in     "$REPO_ROOT/services/bigbird-ai-gateway/app/__init__.py"     "$REPO_ROOT/services/bigbird-ai-gateway/app/library_engine.py"     "$REPO_ROOT/services/bigbird-ai-gateway/app/main.py"     "$REPO_ROOT/server/ava_contacts_gateway.py"     "$REPO_ROOT/server/phone_intelligence_gateway.py"     "$UNIT_SOURCE"
do
    [ -f "$source" ] || { echo "missing source: $source" >&2; exit 4; }
done

python3 -m py_compile     "$REPO_ROOT/services/bigbird-ai-gateway/app/library_engine.py"     "$REPO_ROOT/services/bigbird-ai-gateway/app/main.py"     "$REPO_ROOT/server/ava_contacts_gateway.py"     "$REPO_ROOT/server/phone_intelligence_gateway.py"

HEAD=$(repo_git rev-parse HEAD 2>/dev/null || printf unknown)
BRANCH=$(repo_git branch --show-current 2>/dev/null || true)
DIRTY=$(repo_git status --porcelain 2>/dev/null || printf unknown)

echo "Ava read-only gateway commissioning preflight"
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
[ -f /etc/edge1-operations-api.secret ] || { echo "Operations API credential is unavailable" >&2; exit 4; }

if ! getent group bigbird-ai >/dev/null; then groupadd --system bigbird-ai; fi
if ! getent passwd bigbird-ai >/dev/null; then
    useradd --system --gid bigbird-ai --home-dir /nonexistent --shell /usr/sbin/nologin bigbird-ai
fi

RELEASE="$RELEASES/$HEAD"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$EVIDENCE_ROOT/$STAMP"
install -d -m 0700 "$EVIDENCE"
printf '%s
' "$HEAD" > "$EVIDENCE/repository-commit.txt"

WAS_ENABLED=0
WAS_ACTIVE=0
HAD_UNIT=0
CREATED_RELEASE=0
PREVIOUS_RUNTIME=
systemctl is-enabled --quiet "$SERVICE" 2>/dev/null && WAS_ENABLED=1 || true
systemctl is-active --quiet "$SERVICE" 2>/dev/null && WAS_ACTIVE=1 || true
[ -f "$UNIT_TARGET" ] && { HAD_UNIT=1; cp -a "$UNIT_TARGET" "$EVIDENCE/unit.before"; }
if [ -L "$CURRENT" ]; then PREVIOUS_RUNTIME=$(readlink -f "$CURRENT" || true); fi
printf '%s
' "$PREVIOUS_RUNTIME" > "$EVIDENCE/runtime.before"

rollback() {
    rc=$?
    trap - EXIT INT TERM
    echo "Ava gateway commissioning failed; restoring prior service state." >&2
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
    if [ "$CREATED_RELEASE" -eq 1 ]; then rm -rf "$RELEASE"; fi
    exit "$rc"
}
trap rollback EXIT INT TERM

install -d -m 0755 -o root -g root "$RUNTIME_ROOT" "$RELEASES"
if [ ! -d "$RELEASE" ]; then
    install -d -m 0755 -o root -g root "$RELEASE" "$RELEASE/app" "$RELEASE/server"
    CREATED_RELEASE=1
fi

install -m 0444 -o root -g root "$REPO_ROOT/services/bigbird-ai-gateway/app/__init__.py" "$RELEASE/app/__init__.py"
install -m 0444 -o root -g root "$REPO_ROOT/services/bigbird-ai-gateway/app/library_engine.py" "$RELEASE/app/library_engine.py"
install -m 0555 -o root -g root "$REPO_ROOT/services/bigbird-ai-gateway/app/main.py" "$RELEASE/app/main.py"
install -m 0444 -o root -g root "$REPO_ROOT/server/ava_contacts_gateway.py" "$RELEASE/server/ava_contacts_gateway.py"
install -m 0444 -o root -g root "$REPO_ROOT/server/phone_intelligence_gateway.py" "$RELEASE/server/phone_intelligence_gateway.py"

cmp -s "$REPO_ROOT/services/bigbird-ai-gateway/app/library_engine.py" "$RELEASE/app/library_engine.py"
cmp -s "$REPO_ROOT/services/bigbird-ai-gateway/app/main.py" "$RELEASE/app/main.py"
cmp -s "$REPO_ROOT/server/ava_contacts_gateway.py" "$RELEASE/server/ava_contacts_gateway.py"
cmp -s "$REPO_ROOT/server/phone_intelligence_gateway.py" "$RELEASE/server/phone_intelligence_gateway.py"

ln -sfn "$RELEASE" "$CURRENT.new"
mv -Tf "$CURRENT.new" "$CURRENT"
[ "$(readlink -f "$CURRENT")" = "$RELEASE" ]

if [ ! -f "$ENV_FILE" ]; then
    relay_secret=$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)
    umask 0077
    cat > "$ENV_FILE" <<EOF
BB_RELAY_KEY_ID=edge1-ava-rebuild
BB_RELAY_SECRET=$relay_secret
BB_OPENAI_MODEL=gpt-5-mini
EOF
    chown root:bigbird-ai "$ENV_FILE"
    chmod 0640 "$ENV_FILE"
fi
grep -q '^BB_RELAY_KEY_ID=' "$ENV_FILE" || { echo "gateway relay key id is not configured" >&2; exit 4; }
grep -q '^BB_RELAY_SECRET=' "$ENV_FILE" || { echo "gateway relay secret is not configured" >&2; exit 4; }

install -m 0644 -o root -g root "$UNIT_SOURCE" "$UNIT_TARGET"
systemctl daemon-reload
systemd-analyze verify "$UNIT_TARGET" 2> "$EVIDENCE/systemd-verify.txt"

if [ "$START" -eq 1 ]; then
    systemctl enable "$SERVICE" >/dev/null
    if [ "$WAS_ACTIVE" -eq 1 ]; then systemctl restart "$SERVICE"; else systemctl start "$SERVICE"; fi
    systemctl is-active --quiet "$SERVICE"
    python3 - <<'PY' > "$EVIDENCE/health.json"
import json, time, urllib.request
url = "http://127.0.0.1:8787/healthz"
last = None
for _ in range(20):
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            payload = json.load(response)
        if response.status == 200 and payload.get("status") == "ok" and payload.get("mode") == "read-only":
            print(json.dumps(payload, sort_keys=True))
            raise SystemExit(0)
        last = payload
    except Exception as exc:
        last = str(exc)
    time.sleep(0.25)
raise SystemExit("Ava gateway health check failed: %r" % (last,))
PY
    ss -ltn | grep -Eq '127\.0\.0\.1:8787[[:space:]]' || { echo "loopback listener 8787 not found" >&2; exit 5; }
    systemctl status "$SERVICE" --no-pager > "$EVIDENCE/service-status.txt"
else
    echo "Installed but not started; activation remains explicit." > "$EVIDENCE/service-status.txt"
fi

printf '%s
' "$(readlink -f "$CURRENT")" > "$EVIDENCE/runtime.after"
sha256sum "$UNIT_TARGET" "$RELEASE/app/main.py" "$RELEASE/app/library_engine.py"     "$RELEASE/server/ava_contacts_gateway.py" "$RELEASE/server/phone_intelligence_gateway.py"     > "$EVIDENCE/installed-files.sha256"
trap - EXIT INT TERM
echo "Ava gateway commissioning completed. Runtime: $RELEASE"
echo "Evidence: $EVIDENCE"
echo "Provider egress remains a separate explicit drop-in decision."
