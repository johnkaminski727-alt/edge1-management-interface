#!/bin/bash
set -Eeuo pipefail
umask 077

AUTHORIZATION=WWCX-EDGE1-OPERATOR-CONTROLS-DISABLED-001
REPO=/opt/edge1-management-interface
OPS_RUNTIME_ROOT=/opt/edge1-operations-api-runtimes
OPERATOR_RUNTIME_ROOT=/opt/edge1-operator-mcp-runtimes
APPROVAL_MARKER=/etc/wwcx-edge1-operator/telephony-console-control.json
BROKER_INSTALL=deploy/edge1-operator/install-privileged-broker-v1.sh
OPS_PIN=deploy/pin-edge1-operations-api-runtime.sh
OPERATOR_PIN=deploy/pin-edge1-operator-mcp-runtime.sh
LIVE_VALIDATOR=tools/operator/validate_controls_disabled_live.py
EXPECTED_COMMIT=

fail() { echo "ERROR: $*" >&2; exit 1; }
usage() {
  echo "usage: bash $0 --authorization $AUTHORIZATION --expected-commit <40-hex-sha> --execute" >&2
}

if [ "$#" -ne 5 ] || [ "$1" != --authorization ] || [ "$2" != "$AUTHORIZATION" ] || [ "$3" != --expected-commit ] || [ "$5" != --execute ]; then
  usage
  exit 2
fi
EXPECTED_COMMIT=$4
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail "expected commit must be a full 40-hex SHA"
[ "$(id -u)" -ne 0 ] || fail "run as the authenticated wwadmin user, not root"
[ "$(id -un)" = wwadmin ] || fail "expected authenticated user wwadmin"
[ "$(hostname -f)" = edge1.ww.cx ] || fail "expected edge1.ww.cx"
[ -d "$REPO/.git" ] || fail "repository missing"
cd "$REPO"
[ "$(git branch --show-current)" = main ] || fail "primary checkout must be on main"
[ -z "$(git status --porcelain)" ] || fail "primary checkout has local changes"

for rel in "$BROKER_INSTALL" "$OPS_PIN" "$OPERATOR_PIN" "$LIVE_VALIDATOR" server/asterisk_process_identity.py; do
  [ -f "$REPO/$rel" ] || fail "required reviewed asset missing: $rel"
done

BEFORE_HEAD=$(git rev-parse HEAD)
git fetch origin
REMOTE=$(git rev-parse origin/main)
[ "$REMOTE" = "$EXPECTED_COMMIT" ] || fail "origin/main $REMOTE does not equal reviewed commit $EXPECTED_COMMIT"
if [ "$BEFORE_HEAD" != "$EXPECTED_COMMIT" ]; then
  SAFETY="safety/operator-controls-disabled-$(date -u +%Y%m%dT%H%M%SZ)"
  git branch "$SAFETY" "$BEFORE_HEAD"
  echo "safety_branch=$SAFETY"
  git pull --ff-only origin main
fi
[ "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT" ] || fail "primary checkout did not reach reviewed commit"
[ -z "$(git status --porcelain)" ] || fail "primary checkout became dirty"

# Approval of a Telephony runtime is intentionally a later activation step.
if sudo test -e "$APPROVAL_MARKER"; then
  fail "approved-runtime marker already exists; reconcile before disabled commissioning"
fi

SHORT=${EXPECTED_COMMIT:0:12}
OPS_RUNTIME=$OPS_RUNTIME_ROOT/$SHORT
OPERATOR_RUNTIME=$OPERATOR_RUNTIME_ROOT/$SHORT
sudo install -d -o wwadmin -g wwadmin -m 0755 "$OPS_RUNTIME_ROOT" "$OPERATOR_RUNTIME_ROOT"

prepare_worktree() {
  path=$1
  if [ -e "$path" ]; then
    [ -e "$path/.git" ] || fail "existing runtime is not a Git worktree: $path"
    [ "$(git -C "$path" rev-parse HEAD)" = "$EXPECTED_COMMIT" ] || fail "runtime revision mismatch: $path"
    [ -z "$(git -C "$path" status --porcelain)" ] || fail "runtime is dirty: $path"
  else
    git worktree add --detach "$path" "$EXPECTED_COMMIT"
  fi
}
prepare_worktree "$OPS_RUNTIME"
prepare_worktree "$OPERATOR_RUNTIME"

ASTERISK_PID_BEFORE=$(PYTHONPATH="$REPO/server" python3 -c 'from asterisk_process_identity import resolve_asterisk_pid; print(resolve_asterisk_pid()[0])')
MESSAGING_PID_BEFORE=$(systemctl show wwcx-messaging-gateway.service -p MainPID --value)
TELEPHONY_PID_BEFORE=$(systemctl show wwcx-telephony-console.service -p MainPID --value)
TUNNEL_PID_BEFORE=$(systemctl show edge1-secure-mcp-tunnel.service -p MainPID --value)
for value in "$ASTERISK_PID_BEFORE" "$MESSAGING_PID_BEFORE" "$TELEPHONY_PID_BEFORE" "$TUNNEL_PID_BEFORE"; do
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || fail "required protected process PID is unavailable"
done

BROKER_ROLLBACK=
OPS_ROLLBACK=
OPERATOR_ROLLBACK=
rollback_armed=1
rollback_all() {
  status=$?
  trap - ERR INT TERM
  if [ "${rollback_armed:-0}" -eq 1 ]; then
    echo "Commissioning failed; applying available control-plane rollbacks." >&2
    if [ -n "$OPERATOR_ROLLBACK" ]; then sudo "$OPERATOR_ROLLBACK" || true; fi
    if [ -n "$OPS_ROLLBACK" ]; then sudo "$OPS_ROLLBACK" || true; fi
    if [ -n "$BROKER_ROLLBACK" ]; then sudo "$BROKER_ROLLBACK" || true; fi
  fi
  exit "$status"
}
trap rollback_all ERR INT TERM

BROKER_OUT=$(sudo bash "$REPO/$BROKER_INSTALL" --expected-commit "$EXPECTED_COMMIT" --apply)
printf '%s\n' "$BROKER_OUT"
BROKER_ROLLBACK=$(printf '%s\n' "$BROKER_OUT" | awk -F= '$1 == "rollback" {print $2; exit}')
[ -n "$BROKER_ROLLBACK" ] || fail "broker installer did not return rollback path"

OPS_OUT=$(sudo sh "$REPO/$OPS_PIN" --runtime "$OPS_RUNTIME" --apply)
printf '%s\n' "$OPS_OUT"
OPS_ROLLBACK=$(printf '%s\n' "$OPS_OUT" | awk -F= '$1 == "rollback" {print $2; exit}')
[ -n "$OPS_ROLLBACK" ] || fail "Operations API pin did not return rollback path"

OPERATOR_OUT=$(sudo sh "$REPO/$OPERATOR_PIN" --runtime "$OPERATOR_RUNTIME" --apply)
printf '%s\n' "$OPERATOR_OUT"
OPERATOR_ROLLBACK=$(printf '%s\n' "$OPERATOR_OUT" | awk -F= '$1 == "rollback" {print $2; exit}')
[ -n "$OPERATOR_ROLLBACK" ] || fail "Operator MCP pin did not return rollback path"

sudo python3 "$REPO/$LIVE_VALIDATOR"

ASTERISK_PID_AFTER=$(PYTHONPATH="$REPO/server" python3 -c 'from asterisk_process_identity import resolve_asterisk_pid; print(resolve_asterisk_pid()[0])')
MESSAGING_PID_AFTER=$(systemctl show wwcx-messaging-gateway.service -p MainPID --value)
TELEPHONY_PID_AFTER=$(systemctl show wwcx-telephony-console.service -p MainPID --value)
TUNNEL_PID_AFTER=$(systemctl show edge1-secure-mcp-tunnel.service -p MainPID --value)
[ "$ASTERISK_PID_AFTER" = "$ASTERISK_PID_BEFORE" ] || fail "Asterisk PID changed during disabled commissioning"
[ "$MESSAGING_PID_AFTER" = "$MESSAGING_PID_BEFORE" ] || fail "Messaging Gateway PID changed during disabled commissioning"
[ "$TELEPHONY_PID_AFTER" = "$TELEPHONY_PID_BEFORE" ] || fail "Telephony Console PID changed during disabled commissioning"
[ "$TUNNEL_PID_AFTER" = "$TUNNEL_PID_BEFORE" ] || fail "Secure MCP Tunnel PID changed during disabled commissioning"
sudo test ! -e "$APPROVAL_MARKER" || fail "approval marker appeared unexpectedly"

rollback_armed=0
trap - ERR INT TERM

echo "Edge1 Operator Controls v1 disabled commissioning accepted."
echo "commit=$EXPECTED_COMMIT"
echo "operations_runtime=$OPS_RUNTIME"
echo "operator_runtime=$OPERATOR_RUNTIME"
echo "privileged_broker_installed=true"
echo "legacy_mutations_enabled=false"
echo "telephony_safe_gate_enabled=false"
echo "telephony_safe_scope_present=false"
echo "approved_runtime_marker_present=false"
echo "asterisk_restarted=false"
echo "messaging_gateway_restarted=false"
echo "telephony_console_restarted=false"
echo "secure_mcp_tunnel_restarted=false"
echo "calls_or_messages_generated=false"
