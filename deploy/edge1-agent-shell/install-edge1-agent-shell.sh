#!/bin/sh
set -eu

APPLY=0
REPO=/opt/edge1-management-interface
ROOT=/opt/edge1-agent-shell
UNIT=/etc/systemd/system/edge1-agent-shell.service
TOKEN=/etc/edge1-operator/mcp-token
PORT=8114

usage() {
  echo "usage: $0 [--repo PATH] [--apply]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      REPO=$2
      shift 2
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

PACKAGE="$REPO/tools/mcp/edge1-agent-shell"
SERVICE_SOURCE="$REPO/deploy/edge1-agent-shell/edge1-agent-shell.service"

command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "node is required" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 1; }
command -v systemctl >/dev/null 2>&1 || { echo "systemctl is required" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || { echo "installer must run as root" >&2; exit 1; }
[ -d "$REPO/.git" ] || { echo "repo is not a Git checkout: $REPO" >&2; exit 1; }
[ -f "$PACKAGE/package.json" ] || { echo "missing agent shell package" >&2; exit 1; }
[ -f "$PACKAGE/src/index.js" ] || { echo "missing agent shell entrypoint" >&2; exit 1; }
[ -f "$SERVICE_SOURCE" ] || { echo "missing systemd unit source" >&2; exit 1; }
[ -f "$TOKEN" ] || { echo "missing existing Edge1 MCP token file" >&2; exit 1; }

SHA=$(git -C "$REPO" rev-parse HEAD)
case "$SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "unable to resolve repository commit" >&2; exit 1 ;;
esac
[ "${#SHA}" -eq 40 ] || { echo "repository commit is not a full SHA" >&2; exit 1; }

node --check "$PACKAGE/src/index.js"

printf '%s\n' "Edge1 Agent Shell preflight"
printf 'repo=%s\n' "$REPO"
printf 'commit=%s\n' "$SHA"
printf 'mode=%s\n' "full"
printf 'listen=%s\n' "127.0.0.1:$PORT"
printf 'token_file=%s\n' "$TOKEN"
printf 'runtime_root=%s\n' "$ROOT"
printf 'apply=%s\n' "$APPLY"

if [ "$APPLY" -ne 1 ]; then
  echo "dry-run only; pass --apply to install"
  exit 0
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="/var/backups/wwcx-edge1-agent-shell-$STAMP"
RELEASES="$ROOT/releases"
RELEASE="$RELEASES/$SHA"
TMP="$RELEASES/.tmp-$SHA-$$"
STATE_DIR=/var/lib/edge1-agent-shell
LOG_DIR=/var/log/wwcx-edge1-agent-shell
CURRENT="$ROOT/current"
PREVIOUS="$ROOT/previous"
OLD_CURRENT=

mkdir -p "$BACKUP" "$RELEASES" "$STATE_DIR" "$LOG_DIR"
chmod 700 "$BACKUP" "$STATE_DIR" "$LOG_DIR"

if [ -L "$CURRENT" ]; then
  OLD_CURRENT=$(readlink -f "$CURRENT" || true)
  printf '%s\n' "$OLD_CURRENT" > "$BACKUP/previous-current.txt"
fi
if [ -f "$UNIT" ]; then
  cp -a "$UNIT" "$BACKUP/edge1-agent-shell.service"
else
  : > "$BACKUP/unit-was-absent"
fi

if [ ! -d "$RELEASE" ]; then
  rm -rf "$TMP"
  mkdir -p "$TMP/src"
  cp "$PACKAGE/package.json" "$TMP/package.json"
  cp "$PACKAGE/README.md" "$TMP/README.md"
  cp "$PACKAGE/src/index.js" "$TMP/src/index.js"
  (
    cd "$TMP"
    npm install --omit=dev --ignore-scripts --no-audit --no-fund
    npm run check
  )
  chmod -R go-w "$TMP"
  mv "$TMP" "$RELEASE"
fi

install -m 0644 "$SERVICE_SOURCE" "$UNIT"

if [ -n "$OLD_CURRENT" ] && [ "$OLD_CURRENT" != "$RELEASE" ]; then
  ln -sfn "$OLD_CURRENT" "$PREVIOUS.new"
  mv -Tf "$PREVIOUS.new" "$PREVIOUS"
fi
ln -sfn "$RELEASE" "$CURRENT.new"
mv -Tf "$CURRENT.new" "$CURRENT"

rollback() {
  echo "Agent Shell postflight failed; attempting rollback" >&2
  if [ -n "$OLD_CURRENT" ] && [ -d "$OLD_CURRENT" ]; then
    ln -sfn "$OLD_CURRENT" "$CURRENT.rollback"
    mv -Tf "$CURRENT.rollback" "$CURRENT"
    systemctl daemon-reload || true
    systemctl restart edge1-agent-shell.service || true
  else
    systemctl disable --now edge1-agent-shell.service >/dev/null 2>&1 || true
  fi
}
trap rollback HUP INT TERM

systemctl daemon-reload
systemctl enable --now edge1-agent-shell.service

ATTEMPT=0
HEALTH=
while [ "$ATTEMPT" -lt 20 ]; do
  HEALTH=$(curl -fsS --max-time 2 "http://127.0.0.1:$PORT/healthz" 2>/dev/null || true)
  case "$HEALTH" in
    *'"status":"ok"'*'"mode":"full"'*) break ;;
  esac
  ATTEMPT=$((ATTEMPT + 1))
  sleep 0.5
done
case "$HEALTH" in
  *'"status":"ok"'*'"mode":"full"'*) ;;
  *) rollback; trap - HUP INT TERM; echo "health verification failed" >&2; exit 1 ;;
esac

LISTEN=$(ss -lnt 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $4}')
[ "$LISTEN" = "127.0.0.1:$PORT" ] || {
  rollback
  trap - HUP INT TERM
  echo "listener verification failed: $LISTEN" >&2
  exit 1
}

python3 - "$STATE_DIR/state.json" "$SHA" "$OLD_CURRENT" "$BACKUP" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path, commit, previous, backup = sys.argv[1:]
payload = {
    "schema": "wwcx.edge1-agent-shell.state.v1",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "mode": "full",
    "current_commit": commit,
    "previous_release": previous or None,
    "backup": backup,
    "listener": "127.0.0.1:8114",
    "mcp_path": "/mcp",
}
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
    fh.flush()
    os.fsync(fh.fileno())
os.replace(tmp, path)
os.chmod(path, 0o600)
PY

cat > "$BACKUP/rollback.sh" <<EOF
#!/bin/sh
set -eu
if [ -n '$OLD_CURRENT' ] && [ -d '$OLD_CURRENT' ]; then
  ln -sfn '$OLD_CURRENT' '$CURRENT.rollback'
  mv -Tf '$CURRENT.rollback' '$CURRENT'
  systemctl daemon-reload
  systemctl restart edge1-agent-shell.service
else
  systemctl disable --now edge1-agent-shell.service
fi
EOF
chmod 700 "$BACKUP/rollback.sh"

trap - HUP INT TERM
printf 'installed_release=%s\n' "$RELEASE"
printf 'current=%s\n' "$(readlink -f "$CURRENT")"
printf 'previous=%s\n' "$(readlink -f "$PREVIOUS" 2>/dev/null || true)"
printf 'backup=%s\n' "$BACKUP"
printf 'health=%s\n' "$HEALTH"
printf 'listener=%s\n' "$LISTEN"
