#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/suricata-protected-retention}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
BACKUP_DIR="$EVIDENCE_DIR/rollback"
SERVICE=wwcx-suricata-protected-retention.service
TIMER=wwcx-suricata-protected-retention.timer
DATA_DIR=/var/lib/bigbird-security/suricata-history
POLICY=/etc/wwcx/security/suricata-protected-retention-runtime.json
UNIT_DIR=/etc/systemd/system
MUTATED=0
ROLLED_BACK=false

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
backup() { local p=$1 n=$2; if [ -e "$p" ] || [ -L "$p" ]; then cp -a "$p" "$BACKUP_DIR/$n"; else : >"$BACKUP_DIR/$n.absent"; fi; }
restore() { local p=$1 n=$2; rm -f "$p"; if [ -e "$BACKUP_DIR/$n" ] || [ -L "$BACKUP_DIR/$n" ]; then cp -a "$BACKUP_DIR/$n" "$p"; fi; }
rollback() {
  local rc=$?
  if [ "$MUTATED" -eq 1 ]; then
    ROLLED_BACK=true
    systemctl disable --now "$TIMER" >/dev/null 2>&1 || true
    restore "$UNIT_DIR/$SERVICE" service
    restore "$UNIT_DIR/$TIMER" timer
    restore "$POLICY" policy
    systemctl daemon-reload || true
    if [ "${TIMER_ENABLED_BEFORE:-disabled}" = enabled ]; then systemctl enable "$TIMER" >/dev/null 2>&1 || true; fi
    if [ "${TIMER_ACTIVE_BEFORE:-inactive}" = active ]; then systemctl start "$TIMER" >/dev/null 2>&1 || true; fi
  fi
  printf 'rolled_back=%s\nexit_code=%s\n' "$ROLLED_BACK" "$rc" >"$EVIDENCE_DIR/result.txt"
  find "$EVIDENCE_DIR" -type f ! -name manifest.sha256 -print0 | sort -z | xargs -0 -r sha256sum >"$EVIDENCE_DIR/manifest.sha256" || true
  exit "$rc"
}
trap rollback ERR INT TERM

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found"
[ "$(git -C "$REPO_ROOT" branch --show-current)" = main ] || fail "deployment requires main"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository must be clean"
install -d -o root -g root -m 0700 "$EVIDENCE_DIR" "$BACKUP_DIR"
python3 "$REPO_ROOT/tests/validate_edge1_security_completion.py" | tee "$EVIDENCE_DIR/repository-validation.txt"
[ -f /var/lib/bigbird/operations-center/latest.json ] || fail "sanitized Suricata source is unavailable"

systemctl show suricata.service -p LoadState -p ActiveState -p SubState -p FragmentPath >"$EVIDENCE_DIR/suricata-before.txt" 2>&1 || true
systemctl show wwcx-network-defense.timer -p ActiveState -p UnitFileState >"$EVIDENCE_DIR/network-defense-timer-before.txt" 2>&1 || true
ss -H -lntup 2>/dev/null | sort >"$EVIDENCE_DIR/listeners-before.txt" || true
if command -v nft >/dev/null 2>&1; then nft -j list ruleset 2>/dev/null | sha256sum >"$EVIDENCE_DIR/nftables-before.sha256" || true; fi
if [ -d /etc/suricata ]; then find /etc/suricata -xdev -type f -print0 | sort -z | xargs -0 -r sha256sum >"$EVIDENCE_DIR/suricata-config-before.sha256"; fi
TIMER_ENABLED_BEFORE=$(systemctl is-enabled "$TIMER" 2>/dev/null || true)
TIMER_ACTIVE_BEFORE=$(systemctl is-active "$TIMER" 2>/dev/null || true)
backup "$UNIT_DIR/$SERVICE" service
backup "$UNIT_DIR/$TIMER" timer
backup "$POLICY" policy

install -d -o root -g root -m 0755 /etc/wwcx/security
install -d -o root -g root -m 0700 "$DATA_DIR"
install -o root -g root -m 0600 "$REPO_ROOT/config/security/suricata-protected-retention-runtime.json" "$POLICY"
install -o root -g root -m 0644 "$REPO_ROOT/deploy/systemd/$SERVICE" "$UNIT_DIR/$SERVICE"
install -o root -g root -m 0644 "$REPO_ROOT/deploy/systemd/$TIMER" "$UNIT_DIR/$TIMER"
MUTATED=1
systemctl daemon-reload
systemctl start "$SERVICE"
python3 - "$POLICY" "$DATA_DIR/alerts.sqlite3" "$DATA_DIR/status.json" "$EVIDENCE_DIR/runtime-verification.json" <<'PY'
import json, pathlib, sqlite3, stat, sys
policy=json.loads(pathlib.Path(sys.argv[1]).read_text())
db=pathlib.Path(sys.argv[2]); status=pathlib.Path(sys.argv[3])
if not db.is_file() or not status.is_file(): raise SystemExit('retention outputs missing')
if stat.S_IMODE(db.parent.stat().st_mode) != 0o700 or stat.S_IMODE(db.stat().st_mode) != 0o600 or stat.S_IMODE(status.stat().st_mode) != 0o600: raise SystemExit('retention permissions invalid')
with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as connection:
    integrity=connection.execute('PRAGMA quick_check').fetchone()[0]
    count=connection.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]
    pages=connection.execute('PRAGMA page_count').fetchone()[0]
    page_size=connection.execute('PRAGMA page_size').fetchone()[0]
if integrity != 'ok' or count > int(policy['storage']['max_events']) or pages*page_size > int(policy['storage']['max_database_bytes']): raise SystemExit('retention integrity or capacity invalid')
value={'integrity':'ok','retained':count,'database_bytes':pages*page_size,'database_mode':'0600','directory_mode':'0700','status_mode':'0600'}
pathlib.Path(sys.argv[4]).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
PY
systemctl enable --now "$TIMER"
systemctl is-active --quiet "$TIMER"

systemctl start "$SERVICE"
python3 - "$DATA_DIR/status.json" "$EVIDENCE_DIR/deduplication-acceptance.json" <<'PY'
import json, pathlib, sys
value=json.loads(pathlib.Path(sys.argv[1]).read_text())
if value.get('accepted') != 0 or int(value.get('duplicate', 0)) < 0:
    raise SystemExit('second run did not demonstrate a no-new-row result')
pathlib.Path(sys.argv[2]).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
PY
systemctl show "$SERVICE" -p LoadState -p ActiveState -p SubState -p Result -p ExecMainStatus >"$EVIDENCE_DIR/service-after.txt"
systemctl show "$TIMER" -p LoadState -p ActiveState -p UnitFileState -p NextElapseUSecRealtime >"$EVIDENCE_DIR/timer-after.txt"
ss -H -lntup 2>/dev/null | sort >"$EVIDENCE_DIR/listeners-after.txt" || true
cmp -s "$EVIDENCE_DIR/listeners-before.txt" "$EVIDENCE_DIR/listeners-after.txt" || fail "listener state changed"
systemctl show suricata.service -p LoadState -p ActiveState -p SubState -p FragmentPath >"$EVIDENCE_DIR/suricata-after.txt" 2>&1 || true
cmp -s "$EVIDENCE_DIR/suricata-before.txt" "$EVIDENCE_DIR/suricata-after.txt" || fail "Suricata service state changed"
systemctl show wwcx-network-defense.timer -p ActiveState -p UnitFileState >"$EVIDENCE_DIR/network-defense-timer-after.txt" 2>&1 || true
cmp -s "$EVIDENCE_DIR/network-defense-timer-before.txt" "$EVIDENCE_DIR/network-defense-timer-after.txt" || fail "Network Defense timer state changed"
if command -v nft >/dev/null 2>&1; then nft -j list ruleset 2>/dev/null | sha256sum >"$EVIDENCE_DIR/nftables-after.sha256" || true; cmp -s "$EVIDENCE_DIR/nftables-before.sha256" "$EVIDENCE_DIR/nftables-after.sha256" || fail "nftables state changed"; fi
if [ -d /etc/suricata ]; then find /etc/suricata -xdev -type f -print0 | sort -z | xargs -0 -r sha256sum >"$EVIDENCE_DIR/suricata-config-after.sha256"; cmp -s "$EVIDENCE_DIR/suricata-config-before.sha256" "$EVIDENCE_DIR/suricata-config-after.sha256" || fail "Suricata configuration changed"; fi
printf 'rolled_back=false\nstatus=accepted\n' >"$EVIDENCE_DIR/result.txt"
find "$EVIDENCE_DIR" -type f ! -name manifest.sha256 -print0 | sort -z | xargs -0 sha256sum >"$EVIDENCE_DIR/manifest.sha256"
trap - ERR INT TERM
printf '%s\n' "$EVIDENCE_DIR"
