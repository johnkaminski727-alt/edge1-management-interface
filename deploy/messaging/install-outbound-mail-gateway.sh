#!/bin/sh
set -eu

SERVICE_NAME=wwcx-outbound-mail-gateway.service
SERVICE_USER=wwcx-mail-gateway
SERVICE_GROUP=wwcx-mail-gateway
REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
PORT=${PORT:-8104}
EXPECTED_COMMIT=${EXPECTED_COMMIT:-}
UNIT_SOURCE="$REPO_ROOT/deploy/messaging/$SERVICE_NAME"
UNIT_TARGET="/etc/systemd/system/$SERVICE_NAME"
SMOKE_SOURCE="$REPO_ROOT/deploy/messaging/outbound-mail-gateway-smoke-test.sh"
RUNTIME_DIR="$REPO_ROOT/var/outbound-mail"
STATE_DIR=/var/lib/wwcx-outbound-mail
EVIDENCE_ROOT=${EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/outbound-mail-phase-a}
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$TIMESTAMP"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo sh $0" >&2
  exit 1
fi

if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "Repository not found at $REPO_ROOT" >&2
  exit 1
fi

branch=$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)
if [ "$branch" != "main" ]; then
  echo "Refusing deployment from non-main branch: ${branch:-detached}" >&2
  exit 1
fi

if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
  echo "Refusing deployment with tracked working-tree changes." >&2
  git -C "$REPO_ROOT" status --short >&2 || true
  exit 1
fi

head_commit=$(git -C "$REPO_ROOT" rev-parse HEAD)
if [ -n "$EXPECTED_COMMIT" ] && [ "$head_commit" != "$EXPECTED_COMMIT" ]; then
  echo "HEAD $head_commit does not match approved commit $EXPECTED_COMMIT" >&2
  exit 1
fi

for path in \
  "$UNIT_SOURCE" \
  "$SMOKE_SOURCE" \
  "$REPO_ROOT/server/outbound_mail_gateway_server.py" \
  "$REPO_ROOT/config/messaging/outbound-mail-gateway.json" \
  "$REPO_ROOT/config/messaging/outbound-mail-policy.json" \
  "$REPO_ROOT/config/messaging/mail-identities.json"; do
  if [ ! -f "$path" ]; then
    echo "Missing required deployment asset: $path" >&2
    exit 1
  fi
done

python3 - "$REPO_ROOT" "$PORT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
port = int(sys.argv[2])
config = json.loads((root / "config/messaging/outbound-mail-gateway.json").read_text(encoding="utf-8"))
policy = json.loads((root / "config/messaging/outbound-mail-policy.json").read_text(encoding="utf-8"))
identities = json.loads((root / "config/messaging/mail-identities.json").read_text(encoding="utf-8"))
assert config["listen"] == {"host": "127.0.0.1", "port": port}
assert config["enabled"] is False
assert config["deployment_authorized"] is False
assert config["external_delivery_authorized"] is False
assert config["admin"]["send_endpoint_enabled"] is False
assert config["preparation_api"]["enabled"] is False
assert config["provider"]["selected"] == "none"
assert not any(profile["enabled"] for profile in config["provider"]["profiles"].values())
assert policy["enabled"] is False
assert policy["smtp_cutover_authorized"] is False
assert policy["delivery"]["allow_external_submission"] is False
assert policy["delivery"]["allow_live_delivery"] is False
assert identities["sender_selection"]["outbound_activation_authorized"] is False
assert not any(profile["live_enabled"] for profile in identities["sender_profiles"].values())
PY

service_active=false
if systemctl is-active --quiet "$SERVICE_NAME"; then
  service_active=true
fi

if [ "$service_active" = false ] && ss -H -lnt | awk -v suffix=":$PORT" '$4 ~ suffix "$" {found=1} END {exit found ? 0 : 1}'; then
  echo "Port $PORT is already occupied by another listener; no changes made." >&2
  ss -lntp | grep ":$PORT" >&2 || true
  exit 1
fi

install -d -m 0700 "$EVIDENCE_DIR"
{
  date -u +%Y-%m-%dT%H:%M:%SZ
  printf 'host=%s\n' "$(hostname -f 2>/dev/null || hostname)"
  printf 'principal=%s\n' "$(id -un)"
  printf 'repo=%s\n' "$REPO_ROOT"
  printf 'branch=%s\n' "$branch"
  printf 'commit=%s\n' "$head_commit"
  printf 'port=%s\n' "$PORT"
  git -C "$REPO_ROOT" status --short --branch
} > "$EVIDENCE_DIR/preflight.txt" 2>&1

sha256sum \
  "$REPO_ROOT/config/messaging/outbound-mail-gateway.json" \
  "$REPO_ROOT/config/messaging/outbound-mail-policy.json" \
  "$REPO_ROOT/config/messaging/mail-identities.json" \
  "$UNIT_SOURCE" \
  "$SMOKE_SOURCE" > "$EVIDENCE_DIR/source-sha256.txt"

systemctl status "$SERVICE_NAME" --no-pager -l > "$EVIDENCE_DIR/service-before.txt" 2>&1 || true
systemctl is-enabled "$SERVICE_NAME" > "$EVIDENCE_DIR/enabled-before.txt" 2>&1 || true
ss -lntp > "$EVIDENCE_DIR/listeners-before.txt" 2>&1 || true

was_active=false
was_enabled=false
had_unit=false
if systemctl is-active --quiet "$SERVICE_NAME"; then was_active=true; fi
if systemctl is-enabled --quiet "$SERVICE_NAME"; then was_enabled=true; fi
if [ -f "$UNIT_TARGET" ]; then
  had_unit=true
  cp -a "$UNIT_TARGET" "$EVIDENCE_DIR/previous-unit.service"
fi

mutated=false
success=false
rollback() {
  if [ "$success" = true ] || [ "$mutated" = false ]; then
    return
  fi
  echo "Deployment failed; restoring the previous service unit and state." >&2
  if [ "$had_unit" = true ]; then
    install -m 0644 "$EVIDENCE_DIR/previous-unit.service" "$UNIT_TARGET"
  else
    rm -f "$UNIT_TARGET"
  fi
  systemctl daemon-reload || true
  if [ "$was_enabled" = true ]; then
    systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
  else
    systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 || true
  fi
  if [ "$was_active" = true ]; then
    systemctl restart "$SERVICE_NAME" || true
  else
    systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
  fi
  systemctl status "$SERVICE_NAME" --no-pager -l > "$EVIDENCE_DIR/service-after-rollback.txt" 2>&1 || true
}
trap rollback EXIT
trap 'exit 130' HUP INT TERM

if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
  groupadd --system "$SERVICE_GROUP"
fi
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --gid "$SERVICE_GROUP" --home-dir "$STATE_DIR" --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
elif [ "$(id -gn "$SERVICE_USER")" != "$SERVICE_GROUP" ]; then
  echo "Existing service user $SERVICE_USER has unexpected primary group $(id -gn "$SERVICE_USER")." >&2
  exit 1
fi

install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$STATE_DIR"
install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$RUNTIME_DIR"

temporary_unit=$(mktemp)
trap 'rm -f "$temporary_unit"; rollback' EXIT
sed \
  -e "s#/opt/edge1-management-interface#$REPO_ROOT#g" \
  -e "s#--port 8104#--port $PORT#g" \
  "$UNIT_SOURCE" > "$temporary_unit"

mutated=true
install -m 0644 "$temporary_unit" "$UNIT_TARGET"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null
systemctl restart "$SERVICE_NAME"

if ! HOST=127.0.0.1 PORT="$PORT" sh "$SMOKE_SOURCE" > "$EVIDENCE_DIR/smoke-test.txt" 2>&1; then
  cat "$EVIDENCE_DIR/smoke-test.txt" >&2
  systemctl status "$SERVICE_NAME" --no-pager -l > "$EVIDENCE_DIR/service-failure.txt" 2>&1 || true
  journalctl -u "$SERVICE_NAME" -n 100 --no-pager > "$EVIDENCE_DIR/journal-failure.txt" 2>&1 || true
  exit 1
fi

systemctl status "$SERVICE_NAME" --no-pager -l > "$EVIDENCE_DIR/service-after.txt" 2>&1
systemctl show "$SERVICE_NAME" \
  -p ActiveState -p SubState -p UnitFileState -p User -p Group \
  -p ExecStart -p FragmentPath -p MainPID > "$EVIDENCE_DIR/service-properties.txt"
ss -lntp > "$EVIDENCE_DIR/listeners-after.txt" 2>&1
curl -fsS "http://127.0.0.1:$PORT/outbound-mail/healthz" > "$EVIDENCE_DIR/health.json"
curl -fsS "http://127.0.0.1:$PORT/outbound-mail/status" > "$EVIDENCE_DIR/status.json"
journalctl -u "$SERVICE_NAME" -n 100 --no-pager > "$EVIDENCE_DIR/journal-after.txt" 2>&1 || true

(
  cd "$EVIDENCE_DIR"
  find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
)
chmod -R go-rwx "$EVIDENCE_DIR"

success=true
rm -f "$temporary_unit"
trap - EXIT HUP INT TERM

printf '%s\n' "WW.CX outbound mail disabled foundation installed successfully."
printf '%s\n' "Service: $SERVICE_NAME"
printf '%s\n' "Local URL: http://127.0.0.1:$PORT/outbound-mail/"
printf '%s\n' "Evidence: $EVIDENCE_DIR"
printf '%s\n' "External preparation: disabled"
printf '%s\n' "External delivery: disabled"
