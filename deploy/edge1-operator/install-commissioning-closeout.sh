#!/bin/sh
set -eu
LC_ALL=C
export LC_ALL

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
MODE=${1:-}
EXPECTED_REVISION=${2:-}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/edge1-operator-commissioning-closeout}
EVIDENCE_DIR=$EVIDENCE_ROOT/$STAMP
BACKUP_DIR=$EVIDENCE_DIR/backups
OPS_UNIT=/etc/systemd/system/edge1-operations-api.service
SNAPSHOT_SERVICE=/etc/systemd/system/edge1-asterisk-readonly-snapshot.service
SNAPSHOT_TIMER=/etc/systemd/system/edge1-asterisk-readonly-snapshot.timer
SNAPSHOT_FILE=/run/edge1-asterisk-diagnostics/status.json
MUTATION_STARTED=0

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

rollback_on_exit() {
  code=$?
  trap - 0 1 2 15
  if [ "$code" -ne 0 ] && [ "$MUTATION_STARTED" -eq 1 ] && [ -x "$EVIDENCE_DIR/rollback.sh" ]; then
    printf 'Validation failed after mutation; running recorded rollback.\n' >&2
    if "$EVIDENCE_DIR/rollback.sh" > "$EVIDENCE_DIR/rollback-output.txt" 2>&1; then
      printf 'rolled_back=true\noriginal_exit_code=%s\n' "$code" > "$EVIDENCE_DIR/rollback-result.txt"
    else
      printf 'rolled_back=failed\noriginal_exit_code=%s\n' "$code" > "$EVIDENCE_DIR/rollback-result.txt"
      printf 'Automatic rollback reported an error; inspect %s.\n' "$EVIDENCE_DIR" >&2
    fi
  fi
  exit "$code"
}
trap rollback_on_exit 0 1 2 15

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root"
[ -d "$ROOT/.git" ] || fail "repository not found: $ROOT"
[ "$MODE" = "" ] || [ "$MODE" = "--apply" ] || fail "usage: $0 [--apply EXPECTED_REVISION]"
if [ "$MODE" = "--apply" ]; then
  [ -n "$EXPECTED_REVISION" ] || fail "--apply requires the exact reviewed Git revision"
fi

for command in git python3 systemctl systemd-analyze install stat getent id runuser curl ss sha256sum cp rm grep tr seq sleep hostname date; do
  command -v "$command" >/dev/null 2>&1 || fail "required command unavailable: $command"
done

HOST=$(hostname -f 2>/dev/null || hostname)
[ "$HOST" = "edge1.ww.cx" ] || fail "host mismatch: $HOST"
[ "$(git -C "$ROOT" branch --show-current)" = "main" ] || fail "deployment requires main"
[ -z "$(git -C "$ROOT" status --porcelain)" ] || fail "repository has uncommitted or untracked work"
CURRENT_REVISION=$(git -C "$ROOT" rev-parse HEAD)
if [ "$MODE" = "--apply" ]; then
  [ "$CURRENT_REVISION" = "$EXPECTED_REVISION" ] || fail "revision mismatch: expected $EXPECTED_REVISION got $CURRENT_REVISION"
fi

id wwadmin >/dev/null 2>&1 || fail "wwadmin account missing"
id asterisk >/dev/null 2>&1 || fail "asterisk account missing"
getent group bigbird-audit >/dev/null 2>&1 || fail "bigbird-audit group missing"
if id -nG wwadmin | tr ' ' '\n' | grep -qx asterisk; then
  fail "wwadmin unexpectedly has asterisk group authority"
fi

SOCKET_META=$(stat -Lc '%F|%U|%G|%a' /var/run/asterisk/asterisk.ctl 2>/dev/null || true)
[ "$SOCKET_META" = "socket|asterisk|asterisk|664" ] || fail "Asterisk control-socket boundary drift: $SOCKET_META"

for source in \
  "$ROOT/deploy/edge1-operations-api.service" \
  "$ROOT/server/asterisk_readonly_snapshot.py" \
  "$ROOT/server/asterisk_operator_diagnostics.py" \
  "$ROOT/server/edge1_operator_mcp_protocol.py" \
  "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" \
  "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.timer"; do
  [ -f "$source" ] || fail "required reviewed asset missing: $source"
done

python3 -m py_compile \
  "$ROOT/server/asterisk_readonly_snapshot.py" \
  "$ROOT/server/asterisk_operator_diagnostics.py" \
  "$ROOT/server/edge1_operator_mcp_protocol.py"
python3 -m json.tool "$ROOT/config/edge1-operations-allowlist.json" >/dev/null
systemd-analyze verify \
  "$ROOT/deploy/edge1-operations-api.service" \
  "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" \
  "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.timer"

grep -F 'Environment=EDGE1_OPS_HOST=127.0.0.1' "$ROOT/deploy/edge1-operations-api.service" >/dev/null
grep -F 'Environment=EDGE1_OPS_MUTATIONS_ENABLED=false' "$ROOT/deploy/edge1-operations-api.service" >/dev/null
grep -F 'RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK' "$ROOT/deploy/edge1-operations-api.service" >/dev/null
grep -Fx 'CapabilityBoundingSet=' "$ROOT/deploy/edge1-operations-api.service" >/dev/null
grep -Fx 'AmbientCapabilities=' "$ROOT/deploy/edge1-operations-api.service" >/dev/null
! grep -F 'CAP_NET_ADMIN' "$ROOT/deploy/edge1-operations-api.service" >/dev/null

grep -F 'User=asterisk' "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" >/dev/null
grep -F 'Group=bigbird-audit' "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" >/dev/null
grep -F 'RestrictAddressFamilies=AF_UNIX' "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" >/dev/null
grep -F 'NoNewPrivileges=true' "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" >/dev/null
! grep -E 'SupplementaryGroups=asterisk|sudo|CAP_' "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" >/dev/null

systemctl is-active --quiet edge1-operations-api.service || fail "Operations API is not active before deployment"
systemctl is-active --quiet edge1-operator-mcp.service || fail "Edge1 Operator MCP is not active before deployment"
systemctl is-active --quiet edge1-secure-mcp-tunnel.service || fail "Secure MCP Tunnel is not active before deployment"
systemctl is-enabled --quiet edge1-secure-mcp-tunnel.service || fail "Secure MCP Tunnel is not enabled before deployment"
systemctl is-active --quiet bigbird-ai-tunnel.service || fail "Big Bird tunnel is not active before deployment"
curl -fsS http://127.0.0.1:8097/healthz >/dev/null || fail "Operations API health preflight failed"
ss -lnt | grep -F '127.0.0.1:8097' >/dev/null || fail "Operations API loopback listener missing"
! ss -lnt | grep -E '0\.0\.0\.0:8097|\[::\]:8097' >/dev/null || fail "Operations API has a public wildcard listener"
MCP_HTTP_CODE=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8102/mcp 2>/dev/null || true)
[ "$MCP_HTTP_CODE" = "401" ] || fail "local unauthenticated MCP boundary drift: HTTP $MCP_HTTP_CODE"

if [ "$MODE" = "" ]; then
  printf 'Dry run passed for revision %s.\n' "$CURRENT_REVISION"
  printf 'Apply with: sudo %s --apply %s\n' "$0" "$CURRENT_REVISION"
  exit 0
fi

SNAPSHOT_TIMER_ENABLED_BEFORE=$(systemctl is-enabled edge1-asterisk-readonly-snapshot.timer 2>/dev/null || true)
SNAPSHOT_TIMER_ACTIVE_BEFORE=$(systemctl is-active edge1-asterisk-readonly-snapshot.timer 2>/dev/null || true)

install -d -o root -g root -m 0700 "$BACKUP_DIR"
printf '%s\n' "$CURRENT_REVISION" > "$EVIDENCE_DIR/revision.txt"
printf '%s\n' "$SOCKET_META" > "$EVIDENCE_DIR/asterisk-control-socket-metadata.txt"
id wwadmin > "$EVIDENCE_DIR/wwadmin-groups-before.txt"
systemctl is-active edge1-operations-api.service edge1-operator-mcp.service edge1-secure-mcp-tunnel.service bigbird-ai-tunnel.service > "$EVIDENCE_DIR/service-active-before.txt" 2>&1 || true
systemctl is-enabled edge1-secure-mcp-tunnel.service > "$EVIDENCE_DIR/tunnel-enabled-before.txt" 2>&1 || true
printf '%s\n' "$SNAPSHOT_TIMER_ENABLED_BEFORE" > "$EVIDENCE_DIR/snapshot-timer-enabled-before.txt"
printf '%s\n' "$SNAPSHOT_TIMER_ACTIVE_BEFORE" > "$EVIDENCE_DIR/snapshot-timer-active-before.txt"
sha256sum \
  "$ROOT/deploy/edge1-operations-api.service" \
  "$ROOT/server/asterisk_readonly_snapshot.py" \
  "$ROOT/server/asterisk_operator_diagnostics.py" \
  "$ROOT/server/edge1_operator_mcp_protocol.py" \
  "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" \
  "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.timer" \
  > "$EVIDENCE_DIR/reviewed-assets.sha256"

backup_unit() {
  path=$1
  label=$2
  if [ -e "$path" ]; then
    cp -a "$path" "$BACKUP_DIR/$label"
    printf 'present\n' > "$BACKUP_DIR/$label.state"
  else
    printf 'absent\n' > "$BACKUP_DIR/$label.state"
  fi
}

backup_unit "$OPS_UNIT" edge1-operations-api.service
backup_unit "$SNAPSHOT_SERVICE" edge1-asterisk-readonly-snapshot.service
backup_unit "$SNAPSHOT_TIMER" edge1-asterisk-readonly-snapshot.timer

cat > "$EVIDENCE_DIR/rollback.sh" <<EOF
#!/bin/sh
set -eu
systemctl disable --now edge1-asterisk-readonly-snapshot.timer 2>/dev/null || true
restore() {
  path=\$1
  label=\$2
  state=\$(cat "$BACKUP_DIR/\$label.state" 2>/dev/null || printf absent)
  if [ "\$state" = present ]; then
    cp -a "$BACKUP_DIR/\$label" "\$path"
  else
    rm -f "\$path"
  fi
}
restore "$OPS_UNIT" edge1-operations-api.service
restore "$SNAPSHOT_SERVICE" edge1-asterisk-readonly-snapshot.service
restore "$SNAPSHOT_TIMER" edge1-asterisk-readonly-snapshot.timer
systemctl daemon-reload
case "$SNAPSHOT_TIMER_ENABLED_BEFORE" in
  enabled|enabled-runtime) systemctl enable edge1-asterisk-readonly-snapshot.timer >/dev/null 2>&1 || true ;;
  *) systemctl disable edge1-asterisk-readonly-snapshot.timer >/dev/null 2>&1 || true ;;
esac
if [ "$SNAPSHOT_TIMER_ACTIVE_BEFORE" = active ]; then
  systemctl start edge1-asterisk-readonly-snapshot.timer >/dev/null 2>&1 || true
else
  systemctl stop edge1-asterisk-readonly-snapshot.timer >/dev/null 2>&1 || true
fi
systemctl restart edge1-operations-api.service
systemctl restart edge1-operator-mcp.service
EOF
chmod 0700 "$EVIDENCE_DIR/rollback.sh"

MUTATION_STARTED=1
install -o root -g root -m 0644 "$ROOT/deploy/edge1-operations-api.service" "$OPS_UNIT"
install -o root -g root -m 0644 "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.service" "$SNAPSHOT_SERVICE"
install -o root -g root -m 0644 "$ROOT/deploy/systemd/edge1-asterisk-readonly-snapshot.timer" "$SNAPSHOT_TIMER"
systemctl daemon-reload
systemctl enable --now edge1-asterisk-readonly-snapshot.timer
systemctl start edge1-asterisk-readonly-snapshot.service

SNAPSHOT_META=$(stat -Lc '%F|%U|%G|%a' "$SNAPSHOT_FILE" 2>/dev/null || true)
[ "$SNAPSHOT_META" = "regular file|asterisk|bigbird-audit|640" ] || fail "snapshot metadata validation failed: $SNAPSHOT_META"
runuser -u wwadmin -- test -r "$SNAPSHOT_FILE" || fail "wwadmin cannot read bounded snapshot"
runuser -u wwadmin -- python3 "$ROOT/server/asterisk_operator_diagnostics.py" > "$EVIDENCE_DIR/asterisk-diagnostics-post.json"
python3 - "$EVIDENCE_DIR/asterisk-diagnostics-post.json" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding='utf-8'))
assert value.get('status') == 'ok', value
assert value.get('native_cli_status') == 'ok', value
assert value.get('native_diagnostic_source') == 'asterisk-owned-fixed-snapshot', value
assert value.get('read_only') is True, value
PY

systemctl restart edge1-operations-api.service
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8097/healthz > "$EVIDENCE_DIR/operations-health-post.json" 2>/dev/null; then
    break
  fi
  [ "$i" -lt 20 ] || fail "Operations API health failed after restart"
  sleep 1
done

python3 - "$EVIDENCE_DIR/operations-health-post.json" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding='utf-8'))
assert value.get('status') == 'ok', value
assert value.get('mutations_enabled') is False, value
PY

systemctl restart edge1-operator-mcp.service
for i in $(seq 1 20); do
  MCP_HTTP_CODE=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8102/mcp 2>/dev/null || true)
  if [ "$MCP_HTTP_CODE" = "401" ]; then
    break
  fi
  [ "$i" -lt 20 ] || fail "Edge1 Operator MCP bearer boundary failed after restart: HTTP $MCP_HTTP_CODE"
  sleep 1
done

ss -lnt | grep -F '127.0.0.1:8097' > "$EVIDENCE_DIR/operations-loopback-listener-post.txt"
! ss -lnt | grep -E '0\.0\.0\.0:8097|\[::\]:8097' >/dev/null || fail "Operations API became publicly wildcard-bound"
ss -lnt | grep -F '127.0.0.1:8102' > "$EVIDENCE_DIR/mcp-loopback-listener-post.txt"
! ss -lnt | grep -E '0\.0\.0\.0:8102|\[::\]:8102' >/dev/null || fail "MCP became publicly wildcard-bound"
systemctl is-active --quiet edge1-operator-mcp.service || fail "Edge1 Operator MCP regressed"
systemctl is-active --quiet edge1-secure-mcp-tunnel.service || fail "Secure MCP Tunnel regressed"
systemctl is-enabled --quiet edge1-secure-mcp-tunnel.service || fail "Secure MCP Tunnel lost persistence"
systemctl is-active --quiet bigbird-ai-tunnel.service || fail "Big Bird tunnel regressed"
if id -nG wwadmin | tr ' ' '\n' | grep -qx asterisk; then
  fail "wwadmin gained forbidden asterisk group authority"
fi

systemctl status edge1-operations-api.service edge1-operator-mcp.service edge1-asterisk-readonly-snapshot.timer --no-pager > "$EVIDENCE_DIR/service-status-post.txt" 2>&1 || true
stat -Lc 'path=%n type=%F owner=%U group=%G mode=%a' "$SNAPSHOT_FILE" > "$EVIDENCE_DIR/snapshot-metadata-post.txt"
id wwadmin > "$EVIDENCE_DIR/wwadmin-groups-post.txt"
printf 'EDGE1_OPERATOR_COMMISSIONING_CLOSEOUT=PASS\n' > "$EVIDENCE_DIR/result.txt"
MUTATION_STARTED=0
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
