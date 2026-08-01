#!/bin/sh
set -eu

umask 077

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
EXPECTED_COMMIT=${EXPECTED_COMMIT:-}
PHASE_B_PACKAGE_COMMIT=${PHASE_B_PACKAGE_COMMIT:-c55059c2d0230ea273709bbb5a4169b00bb226c1}
READINESS_EVIDENCE=${READINESS_EVIDENCE:-/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness/20260801T174548Z}
SERVICE_NAME=wwcx-outbound-mail-gateway.service
INSTALLER="$REPO_ROOT/deploy/messaging/install-outbound-mail-preparation-api.sh"
RUNTIME_CONFIG=/etc/wwcx/outbound-mail-gateway.json
ENV_FILE=/etc/wwcx/outbound-mail-gateway.env
DROPIN_FILE=/etc/systemd/system/wwcx-outbound-mail-gateway.service.d/20-preparation-api.conf
SECRET_SOURCE=
INSTALLER_SUCCEEDED=false
ACTIVATION_ACCEPTED=false

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

cleanup() {
  if [ -n "$SECRET_SOURCE" ] && [ -e "$SECRET_SOURCE" ]; then
    rm -f -- "$SECRET_SOURCE"
  fi
  SECRET_SOURCE=
}

rollback_if_needed() {
  if [ "$INSTALLER_SUCCEEDED" = true ] && [ "$ACTIVATION_ACCEPTED" != true ]; then
    echo "Phase B1 wrapper verification failed; restoring the Phase A disabled state." >&2
    if ! EXPECTED_COMMIT="$EXPECTED_COMMIT" ACTION=disable sh "$INSTALLER"; then
      echo "WARNING: automatic Phase A restoration failed; inspect the latest Phase B1 evidence before further action." >&2
    fi
  fi
}

on_exit() {
  rc=$?
  trap - EXIT HUP INT TERM
  rollback_if_needed
  cleanup
  exit "$rc"
}

on_signal() {
  trap - EXIT HUP INT TERM
  rollback_if_needed
  cleanup
  exit 130
}

trap on_exit EXIT
trap on_signal HUP INT TERM

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ "$(hostname -f 2>/dev/null || hostname)" = "$EXPECTED_HOST" ] || fail "unexpected host"
[ -n "$EXPECTED_COMMIT" ] || fail "EXPECTED_COMMIT is required"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found at $REPO_ROOT"
[ -f "$INSTALLER" ] || fail "Phase B1 installer is missing"
[ "$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)" = main ] || fail "repository branch is not main"
[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$EXPECTED_COMMIT" ] || fail "repository HEAD does not match EXPECTED_COMMIT"
[ -z "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=all)" ] || fail "repository is not clean"
git -C "$REPO_ROOT" merge-base --is-ancestor "$PHASE_B_PACKAGE_COMMIT" HEAD || fail "Phase B package commit is not an ancestor of HEAD"

protected_paths='deploy/messaging/install-outbound-mail-preparation-api.sh
deploy/messaging/outbound-mail-preparation-api-nginx.conf.example
deploy/messaging/wwcx-outbound-mail-preparation-api.conf
docs/messaging-operations/outbound-mail-phase-b-preparation-20260801.md
server/outbound_mail_gateway.py
server/outbound_mail_gateway_server.py
server/outbound_mail_preparation_auth.py
tools/outbound_mail_preparation_canary.py
config/messaging/outbound-mail-gateway.json
config/messaging/outbound-mail-policy.json
config/messaging/mail-identities.json'
if ! git -C "$REPO_ROOT" diff --quiet "$PHASE_B_PACKAGE_COMMIT"..HEAD -- $protected_paths; then
  git -C "$REPO_ROOT" diff --name-only "$PHASE_B_PACKAGE_COMMIT"..HEAD -- $protected_paths >&2 || true
  fail "protected Phase B files changed after the approved package"
fi

[ -d "$READINESS_EVIDENCE" ] || fail "accepted readiness evidence directory is missing"
[ ! -L "$READINESS_EVIDENCE" ] || fail "readiness evidence directory must not be a symlink"
[ "$(stat -c %u "$READINESS_EVIDENCE")" -eq 0 ] || fail "readiness evidence directory must be root-owned"
case "$(stat -c %a "$READINESS_EVIDENCE")" in
  700) ;;
  *) fail "readiness evidence directory must have mode 0700" ;;
esac
(
  cd "$READINESS_EVIDENCE"
  sha256sum -c SHA256SUMS >/dev/null
) || fail "readiness evidence hash verification failed"
grep -qx 'readiness_state=ready_for_explicit_b1_authorization' "$READINESS_EVIDENCE/summary.txt" || fail "readiness evidence does not authorize the B1 decision"
grep -qx 'secret_generated=no' "$READINESS_EVIDENCE/summary.txt" || fail "readiness evidence secret-generation boundary is inconsistent"
grep -qx 'runtime_files_modified=no' "$READINESS_EVIDENCE/summary.txt" || fail "readiness evidence runtime boundary is inconsistent"
grep -qx 'service_restarted=no' "$READINESS_EVIDENCE/summary.txt" || fail "readiness evidence service boundary is inconsistent"
grep -qx 'proxy_modified=no' "$READINESS_EVIDENCE/summary.txt" || fail "readiness evidence proxy boundary is inconsistent"
grep -qx 'dns_modified=no' "$READINESS_EVIDENCE/summary.txt" || fail "readiness evidence DNS boundary is inconsistent"
grep -qx 'firewall_modified=no' "$READINESS_EVIDENCE/summary.txt" || fail "readiness evidence firewall boundary is inconsistent"
grep -qx 'message_sent=no' "$READINESS_EVIDENCE/summary.txt" || fail "readiness evidence delivery boundary is inconsistent"
[ ! -s "$READINESS_EVIDENCE/failures.txt" ] || fail "readiness evidence contains failures"

for path in "$RUNTIME_CONFIG" "$ENV_FILE" "$DROPIN_FILE"; do
  [ ! -e "$path" ] && [ ! -L "$path" ] || fail "B1 runtime material already exists: $path"
done

systemctl is-active --quiet "$SERVICE_NAME" || fail "$SERVICE_NAME is not active"
systemctl is-enabled --quiet "$SERVICE_NAME" || fail "$SERVICE_NAME is not enabled"
[ "$(systemctl show "$SERVICE_NAME" -p User --value)" = wwcx-mail-gateway ] || fail "unexpected service principal"

port_addresses=$(ss -lnt 2>/dev/null | awk 'NR > 1 {print $4}' | grep -E ':8104$' || true)
[ "$port_addresses" = '127.0.0.1:8104' ] || fail "port 8104 is not isolated to the approved loopback address"

unsigned_code=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/api/v1/status || true)
[ "$unsigned_code" = 403 ] || fail "unsigned preparation status must remain HTTP 403 before B1 activation"
send_code=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8104/outbound-mail/send || true)
[ "$send_code" = 403 ] || fail "send endpoint must remain HTTP 403"

for root in /etc/nginx /etc/apache2 /etc/httpd; do
  if [ -d "$root" ] && grep -R -l --binary-files=without-match 'outbound-mail/api/v1' "$root" >/dev/null 2>&1; then
    fail "a web-server configuration already references the preparation API path"
  fi
done

[ "$(findmnt -n -o FSTYPE /run 2>/dev/null || true)" = tmpfs ] || fail "/run must be a tmpfs before temporary secret generation"
SECRET_SOURCE=$(mktemp /run/wwcx-outbound-mail-b1-secret.XXXXXX)
chown root:root "$SECRET_SOURCE"
chmod 0600 "$SECRET_SOURCE"
python3 - "$SECRET_SOURCE" <<'PY'
import pathlib
import secrets
import sys

path = pathlib.Path(sys.argv[1])
token = secrets.token_urlsafe(48)
if len(token) < 43 or len(token) > 256:
    raise SystemExit("generated token length is outside the accepted range")
if not all(character.isalnum() or character in "_-" for character in token):
    raise SystemExit("generated token is not URL-safe")
path.write_text(token, encoding="ascii")
PY
[ "$(stat -c %u "$SECRET_SOURCE")" -eq 0 ] || fail "temporary secret source is not root-owned"
[ "$(stat -c %a "$SECRET_SOURCE")" = 600 ] || fail "temporary secret source mode is not 0600"
secret_size=$(stat -c %s "$SECRET_SOURCE")
[ "$secret_size" -ge 43 ] && [ "$secret_size" -le 256 ] || fail "temporary secret source size is invalid"

echo "Phase B1 authorization accepted; activating loopback preparation authentication."
echo "The production secret will not be displayed, hashed, or copied into deployment evidence."

EXPECTED_COMMIT="$EXPECTED_COMMIT" \
SECRET_SOURCE_FILE="$SECRET_SOURCE" \
ACTION=install \
sh "$INSTALLER"
INSTALLER_SUCCEEDED=true

rm -f -- "$SECRET_SOURCE"
SECRET_SOURCE=

[ -f "$ENV_FILE" ] || fail "runtime environment file was not installed"
[ "$(stat -c %u "$ENV_FILE")" -eq 0 ] || fail "runtime environment file is not root-owned"
[ "$(stat -c %a "$ENV_FILE")" = 600 ] || fail "runtime environment file mode is not 0600"
[ -f "$RUNTIME_CONFIG" ] || fail "runtime configuration was not installed"
[ -f "$DROPIN_FILE" ] || fail "systemd drop-in was not installed"

curl -fsS --max-time 5 http://127.0.0.1:8104/outbound-mail/status | python3 -c '
import json, sys
status = json.load(sys.stdin)
assert status["state"] == "disabled"
assert status["preparation_api"]["enabled"] is True
assert status["preparation_api"]["runtime_secret_configured"] is True
assert status["external_delivery_enabled"] is False
assert status["policy_enabled"] is False
assert status["sender_selection"]["live_sender_count"] == 0
assert not any(provider["ready"] for provider in status["providers"])
'

send_code=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8104/outbound-mail/send || true)
[ "$send_code" = 403 ] || fail "send endpoint is not disabled after B1 activation"

ACTIVATION_ACCEPTED=true
trap - EXIT HUP INT TERM
cleanup

echo "Phase B1 loopback preparation authentication activated successfully."
echo "B2 reverse proxy: not installed"
echo "External delivery: disabled"
