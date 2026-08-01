#!/bin/sh
set -eu

SERVICE_NAME=wwcx-outbound-mail-gateway.service
REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
EXPECTED_COMMIT=${EXPECTED_COMMIT:-}
ACTION=${ACTION:-install}
SECRET_SOURCE_FILE=${SECRET_SOURCE_FILE:-}
DROPIN_SOURCE="$REPO_ROOT/deploy/messaging/wwcx-outbound-mail-preparation-api.conf"
DROPIN_DIR="/etc/systemd/system/$SERVICE_NAME.d"
DROPIN_TARGET="$DROPIN_DIR/20-preparation-api.conf"
RUNTIME_DIR=/etc/wwcx
RUNTIME_CONFIG="$RUNTIME_DIR/outbound-mail-gateway.json"
ENV_FILE="$RUNTIME_DIR/outbound-mail-gateway.env"
CANARY="$REPO_ROOT/tools/outbound_mail_preparation_canary.py"
EVIDENCE_ROOT=${EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1}
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$TIMESTAMP"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo sh $0" >&2
  exit 1
fi

case "$ACTION" in
  install|disable) ;;
  *) echo "ACTION must be install or disable" >&2; exit 64 ;;
esac

if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "Repository not found at $REPO_ROOT" >&2
  exit 1
fi

branch=$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)
if [ "$branch" != "main" ]; then
  echo "Refusing operation from non-main branch: ${branch:-detached}" >&2
  exit 1
fi
if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
  echo "Refusing operation with tracked working-tree changes." >&2
  git -C "$REPO_ROOT" status --short >&2 || true
  exit 1
fi
head_commit=$(git -C "$REPO_ROOT" rev-parse HEAD)
if [ -n "$EXPECTED_COMMIT" ] && [ "$head_commit" != "$EXPECTED_COMMIT" ]; then
  echo "HEAD $head_commit does not match approved commit $EXPECTED_COMMIT" >&2
  exit 1
fi

for path in \
  "$DROPIN_SOURCE" \
  "$CANARY" \
  "$REPO_ROOT/config/messaging/outbound-mail-gateway.json" \
  "$REPO_ROOT/config/messaging/outbound-mail-policy.json" \
  "$REPO_ROOT/config/messaging/mail-identities.json"; do
  if [ ! -f "$path" ]; then
    echo "Missing required Phase B1 asset: $path" >&2
    exit 1
  fi
done

if ! systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "$SERVICE_NAME must be active before Phase B1" >&2
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
  printf 'action=%s\n' "$ACTION"
  git -C "$REPO_ROOT" status --short --branch
} > "$EVIDENCE_DIR/preflight.txt" 2>&1
systemctl status "$SERVICE_NAME" --no-pager -l > "$EVIDENCE_DIR/service-before.txt" 2>&1 || true
systemctl show "$SERVICE_NAME" -p ActiveState -p SubState -p FragmentPath -p DropInPaths -p EnvironmentFiles > "$EVIDENCE_DIR/service-properties-before.txt"
ss -lntp > "$EVIDENCE_DIR/listeners-before.txt" 2>&1 || true
curl -fsS http://127.0.0.1:8104/outbound-mail/status > "$EVIDENCE_DIR/status-before.json"

python3 - "$REPO_ROOT" <<'PY'
import json
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
config = json.loads((root / "config/messaging/outbound-mail-gateway.json").read_text(encoding="utf-8"))
policy = json.loads((root / "config/messaging/outbound-mail-policy.json").read_text(encoding="utf-8"))
identities = json.loads((root / "config/messaging/mail-identities.json").read_text(encoding="utf-8"))
assert config["listen"] == {"host": "127.0.0.1", "port": 8104}
assert config["enabled"] is False
assert config["external_delivery_authorized"] is False
assert config["admin"]["send_endpoint_enabled"] is False
assert config["preparation_api"]["enabled"] is False
assert config["provider"]["selected"] == "none"
assert not any(profile["enabled"] for profile in config["provider"]["profiles"].values())
assert policy["enabled"] is False
assert policy["smtp_cutover_authorized"] is False
assert policy["delivery"]["allow_external_submission"] is False
assert policy["delivery"]["allow_live_delivery"] is False
assert identities["outbound_activation_authorized"] is False
assert not any(profile["outbound_enabled"] for profile in identities["sender_profiles"].values())
PY

rollback_dir=$(mktemp -d)
chmod 0700 "$rollback_dir"
runtime_tmp=
env_tmp=
dropin_tmp=
success=false
mutated=false

for path in "$DROPIN_TARGET" "$ENV_FILE" "$RUNTIME_CONFIG"; do
  name=$(basename "$path")
  if [ -f "$path" ]; then
    cp -a "$path" "$rollback_dir/$name"
    printf '%s=present mode=%s\n' "$name" "$(stat -c %a "$path")" >> "$EVIDENCE_DIR/prior-runtime-files.txt"
  else
    printf '%s=absent\n' "$name" >> "$EVIDENCE_DIR/prior-runtime-files.txt"
  fi
done

cleanup_temporaries() {
  [ -z "$runtime_tmp" ] || rm -f "$runtime_tmp"
  [ -z "$env_tmp" ] || rm -f "$env_tmp"
  [ -z "$dropin_tmp" ] || rm -f "$dropin_tmp"
  rm -rf "$rollback_dir"
  unset secret 2>/dev/null || true
}

restore_prior() {
  echo "Phase B1 operation failed; restoring prior runtime files and service state." >&2
  install -d -m 0755 "$RUNTIME_DIR" "$DROPIN_DIR"
  for path in "$DROPIN_TARGET" "$ENV_FILE" "$RUNTIME_CONFIG"; do
    name=$(basename "$path")
    if [ -f "$rollback_dir/$name" ]; then
      cp -a "$rollback_dir/$name" "$path"
    else
      rm -f "$path"
    fi
  done
  rmdir "$DROPIN_DIR" 2>/dev/null || true
  systemctl daemon-reload || true
  systemctl restart "$SERVICE_NAME" || true
  systemctl status "$SERVICE_NAME" --no-pager -l > "$EVIDENCE_DIR/service-after-rollback.txt" 2>&1 || true
}

on_exit() {
  rc=$?
  trap - EXIT HUP INT TERM
  if [ "$success" != true ] && [ "$mutated" = true ]; then
    restore_prior
  fi
  cleanup_temporaries
  exit "$rc"
}
on_signal() {
  trap - EXIT HUP INT TERM
  if [ "$success" != true ] && [ "$mutated" = true ]; then
    restore_prior
  fi
  cleanup_temporaries
  exit 130
}
trap on_exit EXIT
trap on_signal HUP INT TERM

if [ "$ACTION" = disable ]; then
  mutated=true
  rm -f "$DROPIN_TARGET" "$ENV_FILE" "$RUNTIME_CONFIG"
  rmdir "$DROPIN_DIR" 2>/dev/null || true
  systemctl daemon-reload
  systemctl restart "$SERVICE_NAME"
  HOST=127.0.0.1 PORT=8104 sh "$REPO_ROOT/deploy/messaging/outbound-mail-gateway-smoke-test.sh" > "$EVIDENCE_DIR/disabled-smoke.txt" 2>&1
  systemctl status "$SERVICE_NAME" --no-pager -l > "$EVIDENCE_DIR/service-after.txt" 2>&1
  systemctl show "$SERVICE_NAME" -p ActiveState -p SubState -p FragmentPath -p DropInPaths -p EnvironmentFiles > "$EVIDENCE_DIR/service-properties-after.txt"
  curl -fsS http://127.0.0.1:8104/outbound-mail/status > "$EVIDENCE_DIR/status-after.json"
  (
    cd "$EVIDENCE_DIR"
    find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
  )
  chmod -R go-rwx "$EVIDENCE_DIR"
  success=true
  cleanup_temporaries
  trap - EXIT HUP INT TERM
  echo "Preparation API disabled and Phase A service restored."
  echo "Evidence: $EVIDENCE_DIR"
  exit 0
fi

if [ -z "$SECRET_SOURCE_FILE" ]; then
  echo "SECRET_SOURCE_FILE is required; secret generation is a separate approved action" >&2
  exit 64
fi
if [ -L "$SECRET_SOURCE_FILE" ] || [ ! -f "$SECRET_SOURCE_FILE" ]; then
  echo "SECRET_SOURCE_FILE must be a regular non-symlink file" >&2
  exit 64
fi
set -- $(stat -c '%u %a %s' "$SECRET_SOURCE_FILE")
secret_uid=$1
secret_mode=$2
secret_size=$3
if [ "$secret_uid" -ne 0 ]; then
  echo "SECRET_SOURCE_FILE must be owned by root" >&2
  exit 77
fi
case "$secret_mode" in
  400|600) ;;
  *) echo "SECRET_SOURCE_FILE mode must be 0400 or 0600" >&2; exit 77 ;;
esac
if [ "$secret_size" -lt 43 ] || [ "$secret_size" -gt 257 ]; then
  echo "SECRET_SOURCE_FILE size is outside the accepted range" >&2
  exit 64
fi
secret=$(cat "$SECRET_SOURCE_FILE")
case "$secret" in
  *[!A-Za-z0-9_-]*|'')
    echo "Secret must be a single URL-safe token containing only A-Z, a-z, 0-9, _ and -" >&2
    exit 64
    ;;
esac
if [ "${#secret}" -lt 43 ] || [ "${#secret}" -gt 256 ]; then
  echo "Secret length must be between 43 and 256 characters" >&2
  exit 64
fi
printf 'secret_length=%s\n' "${#secret}" >> "$EVIDENCE_DIR/preflight.txt"

runtime_tmp=$(mktemp)
env_tmp=$(mktemp)
dropin_tmp=$(mktemp)
python3 - "$REPO_ROOT/config/messaging/outbound-mail-gateway.json" "$runtime_tmp" <<'PY'
import json
import pathlib
import sys
source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
config = json.loads(source.read_text(encoding="utf-8"))
config["preparation_api"]["enabled"] = True
assert config["enabled"] is False
assert config["external_delivery_authorized"] is False
assert config["admin"]["send_endpoint_enabled"] is False
assert config["provider"]["selected"] == "none"
assert not any(profile["enabled"] for profile in config["provider"]["profiles"].values())
target.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
printf 'WWCX_MAIL_GATEWAY_TOKEN=%s\n' "$secret" > "$env_tmp"
unset secret
sed "s#/opt/edge1-management-interface#$REPO_ROOT#g" "$DROPIN_SOURCE" > "$dropin_tmp"

mutated=true
install -d -m 0755 "$RUNTIME_DIR" "$DROPIN_DIR"
install -m 0644 -o root -g root "$runtime_tmp" "$RUNTIME_CONFIG"
install -m 0600 -o root -g root "$env_tmp" "$ENV_FILE"
install -m 0644 -o root -g root "$dropin_tmp" "$DROPIN_TARGET"

sha256sum "$RUNTIME_CONFIG" "$DROPIN_TARGET" > "$EVIDENCE_DIR/runtime-sha256.txt"
cp "$RUNTIME_CONFIG" "$EVIDENCE_DIR/runtime-config.json"
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"

python3 "$CANARY" --secret-file "$SECRET_SOURCE_FILE" > "$EVIDENCE_DIR/canary.txt" 2>&1
systemctl status "$SERVICE_NAME" --no-pager -l > "$EVIDENCE_DIR/service-after.txt" 2>&1
systemctl show "$SERVICE_NAME" -p ActiveState -p SubState -p FragmentPath -p DropInPaths -p EnvironmentFiles -p ExecStart -p MainPID > "$EVIDENCE_DIR/service-properties-after.txt"
ss -lntp > "$EVIDENCE_DIR/listeners-after.txt" 2>&1
curl -fsS http://127.0.0.1:8104/outbound-mail/status > "$EVIDENCE_DIR/status-after.json"
journalctl -u "$SERVICE_NAME" -n 100 --no-pager > "$EVIDENCE_DIR/journal-after.txt" 2>&1 || true

python3 - "$EVIDENCE_DIR/status-after.json" <<'PY'
import json
import pathlib
import sys
status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert status["state"] == "disabled"
assert status["external_delivery_enabled"] is False
assert status["policy_enabled"] is False
assert status["preparation_api"]["enabled"] is True
assert status["preparation_api"]["runtime_secret_configured"] is True
assert status["sender_selection"]["live_sender_count"] == 0
assert not any(item["ready"] for item in status["providers"])
PY

(
  cd "$EVIDENCE_DIR"
  find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
)
chmod -R go-rwx "$EVIDENCE_DIR"

success=true
cleanup_temporaries
trap - EXIT HUP INT TERM

echo "WW.CX outbound mail preparation API enabled on loopback only."
echo "Service: $SERVICE_NAME"
echo "Local URL: http://127.0.0.1:8104/outbound-mail/api/v1/"
echo "Evidence: $EVIDENCE_DIR"
echo "TLS reverse proxy: not installed"
echo "External delivery: disabled"
