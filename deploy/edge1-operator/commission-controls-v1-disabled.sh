#!/bin/bash
set -euo pipefail
umask 077

AUTHORIZATION=WWCX-EDGE1-OPERATOR-CONTROLS-DISABLED-001
REPO=/opt/edge1-management-interface
OPS_RUNTIME_ROOT=/opt/edge1-operations-api-runtimes
OPERATOR_RUNTIME_ROOT=/opt/edge1-operator-mcp-runtimes
OPERATOR_SERVICE_USER=edge1-operator
OPERATOR_SERVICE_GROUP=edge1-operator
APPROVAL_MARKER=/etc/wwcx-edge1-operator/telephony-console-control.json
BROKER_INSTALL=deploy/edge1-operator/install-privileged-broker-v1.sh
OPS_PIN=deploy/pin-edge1-operations-api-runtime.sh
OPERATOR_PIN=deploy/pin-edge1-operator-mcp-runtime.sh
LIVE_VALIDATOR=tools/operator/validate_controls_disabled_live.py
EXPECTED_COMMIT=
REVIEWED_CONTROL_BASE=
DEPLOY_COMMIT=
MODE=

fail() { echo "ERROR: $*" >&2; exit 1; }
usage() {
  echo "usage: bash $0 --authorization $AUTHORIZATION (--expected-commit <40-hex-sha> | --reviewed-control-base <40-hex-sha>) --execute" >&2
}

if [ "$#" -ne 5 ] || [ "$1" != --authorization ] || [ "$2" != "$AUTHORIZATION" ] || [ "$5" != --execute ]; then
  usage
  exit 2
fi
case "$3" in
  --expected-commit)
    MODE=exact
    EXPECTED_COMMIT=$4
    ;;
  --reviewed-control-base)
    MODE=reviewed-base
    REVIEWED_CONTROL_BASE=$4
    ;;
  *)
    usage
    exit 2
    ;;
esac
if [ "$MODE" = exact ]; then
  [[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail "expected commit must be a full 40-hex SHA"
else
  [[ "$REVIEWED_CONTROL_BASE" =~ ^[0-9a-f]{40}$ ]] || fail "reviewed control base must be a full 40-hex SHA"
fi

[ "$(id -u)" -ne 0 ] || fail "run as the authenticated wwadmin user, not root"
[ "$(id -un)" = wwadmin ] || fail "expected authenticated user wwadmin"
[ "$(hostname -f)" = edge1.ww.cx ] || fail "expected edge1.ww.cx"
[ -d "$REPO/.git" ] || fail "repository missing"
cd "$REPO"
[ "$(git branch --show-current)" = main ] || fail "primary checkout must be on main"
[ -z "$(git status --porcelain)" ] || fail "primary checkout has local changes"
getent passwd "$OPERATOR_SERVICE_USER" >/dev/null || fail "Operator service user is unavailable"
getent group "$OPERATOR_SERVICE_GROUP" >/dev/null || fail "Operator service group is unavailable"

BEFORE_HEAD=$(git rev-parse HEAD)
git fetch origin
REMOTE=$(git rev-parse origin/main)

if [ "$MODE" = exact ]; then
  [ "$REMOTE" = "$EXPECTED_COMMIT" ] || fail "origin/main $REMOTE does not equal reviewed commit $EXPECTED_COMMIT"
  DEPLOY_COMMIT=$EXPECTED_COMMIT
else
  git cat-file -e "$REVIEWED_CONTROL_BASE^{commit}" 2>/dev/null || fail "reviewed control base is not present in the local object database"
  git merge-base --is-ancestor "$REVIEWED_CONTROL_BASE" "$REMOTE" || fail "reviewed control base is not an ancestor of origin/main"

  CONTROL_DIFF=$(git diff --name-only "$REVIEWED_CONTROL_BASE..$REMOTE" -- \
    deploy/edge1-operator \
    deploy/pin-edge1-operator-mcp-runtime.sh \
    deploy/pin-edge1-operations-api-runtime.sh \
    deploy/edge1-operations-api.service \
    config/edge1-operator-capabilities.json \
    config/edge1-operations-allowlist.json \
    server/__init__.py \
    server/edge1_operator_http.py \
    server/edge1_operator_entrypoint.py \
    server/edge1_operator_mcp_protocol.py \
    server/edge1_operator_mcp_adapter.py \
    server/edge1_operator_runtime.py \
    server/edge1_operator_capabilities.py \
    server/edge1_operator_operations_client.py \
    server/edge1_operations_api.py \
    server/edge1_operations_typed_actions.py \
    server/asterisk_process_identity.py \
    server/telephony_console_control_status.py \
    server/control_surface_diagnostics.py \
    tools/operator \
    tests/test_edge1_operator_disabled_commissioning.py \
    tests/test_edge1_operator_privileged_broker_v1.py)
  if [ -n "$CONTROL_DIFF" ]; then
    echo "Control-plane paths changed after reviewed base $REVIEWED_CONTROL_BASE:" >&2
    printf '%s\n' "$CONTROL_DIFF" >&2
    fail "fresh control-plane review is required"
  fi
  DEPLOY_COMMIT=$REMOTE
  echo "reviewed_control_base=$REVIEWED_CONTROL_BASE"
  echo "resolved_deploy_commit=$DEPLOY_COMMIT"
fi

if [ "$BEFORE_HEAD" != "$DEPLOY_COMMIT" ]; then
  SAFETY="safety/operator-controls-disabled-$(date -u +%Y%m%dT%H%M%SZ)"
  git branch "$SAFETY" "$BEFORE_HEAD"
  echo "safety_branch=$SAFETY"
  git pull --ff-only origin main
fi
[ "$(git rev-parse HEAD)" = "$DEPLOY_COMMIT" ] || fail "primary checkout did not reach resolved deploy commit"
[ -z "$(git status --porcelain)" ] || fail "primary checkout became dirty"
EXPECTED_COMMIT=$DEPLOY_COMMIT

for rel in "$BROKER_INSTALL" "$OPS_PIN" "$OPERATOR_PIN" "$LIVE_VALIDATOR" server/asterisk_process_identity.py; do
  [ -f "$REPO/$rel" ] || fail "required reviewed asset missing: $rel"
done

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

# The script-wide umask is intentionally 077. Git worktrees created under that
# umask are private to wwadmin, but edge1-operator-mcp.service runs as the
# dedicated edge1-operator identity. Grant that group read/traverse only; do not
# grant it write permission and do not expose the runtime to other users.
sudo chgrp -R "$OPERATOR_SERVICE_GROUP" "$OPERATOR_RUNTIME"
sudo chmod -R g+rX,o-rwx "$OPERATOR_RUNTIME"
sudo -u "$OPERATOR_SERVICE_USER" test -x "$OPERATOR_RUNTIME" || fail "Operator service cannot traverse immutable runtime"
for rel in \
  server/edge1_operator_http.py \
  server/edge1_operator_entrypoint.py \
  server/edge1_operator_runtime.py \
  server/edge1_operator_capabilities.py \
  config/edge1-operator-capabilities.json
do
  sudo -u "$OPERATOR_SERVICE_USER" test -r "$OPERATOR_RUNTIME/$rel" \
    || fail "Operator service cannot read immutable runtime asset: $rel"
done
sudo -u "$OPERATOR_SERVICE_USER" env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$OPERATOR_RUNTIME" \
  python3 -c 'import server.edge1_operator_http' \
  || fail "Operator service identity cannot import immutable runtime"

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

BROKER_LOG=$(mktemp)
sudo bash "$REPO/$BROKER_INSTALL" --expected-commit "$EXPECTED_COMMIT" --apply | tee "$BROKER_LOG"
BROKER_OUT=$(cat "$BROKER_LOG")
rm -f "$BROKER_LOG"
BROKER_ROLLBACK=$(printf '%s\n' "$BROKER_OUT" | awk -F= '$1 == "rollback" {print $2; exit}')
[ -n "$BROKER_ROLLBACK" ] || fail "broker installer did not return rollback path"

OPS_LOG=$(mktemp)
sudo sh "$REPO/$OPS_PIN" --runtime "$OPS_RUNTIME" --apply | tee "$OPS_LOG"
OPS_OUT=$(cat "$OPS_LOG")
rm -f "$OPS_LOG"
OPS_ROLLBACK=$(printf '%s\n' "$OPS_OUT" | awk -F= '$1 == "rollback" {print $2; exit}')
[ -n "$OPS_ROLLBACK" ] || fail "Operations API pin did not return rollback path"

OPERATOR_LOG=$(mktemp)
sudo sh "$REPO/$OPERATOR_PIN" --runtime "$OPERATOR_RUNTIME" --apply | tee "$OPERATOR_LOG"
OPERATOR_OUT=$(cat "$OPERATOR_LOG")
rm -f "$OPERATOR_LOG"
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
if [ "$MODE" = reviewed-base ]; then
  echo "reviewed_control_base=$REVIEWED_CONTROL_BASE"
fi
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
