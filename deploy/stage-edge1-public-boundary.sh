#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/edge1-public-boundary-stage}
AUTH_USER_FILE=${EDGE1_AUTH_USER_FILE:-}
ACCEPTANCE_FILE=${EDGE1_AUTH_ACCEPTANCE_FILE:-}
PUBLIC_BASE=${EDGE1_PUBLIC_BASE_URL:-https://edge1.ww.cx}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
BACKUP_DIR="$EVIDENCE_DIR/rollback"
CONF=/etc/apache2/conf-available/edge1-security-boundary.conf
ENABLED=/etc/apache2/conf-enabled/edge1-security-boundary.conf
SESSION_KEYS=/etc/wwcx/edge1-ops/session.keys
SERVICE=wwcx-edge1-minimized-public-summary.service
TIMER=wwcx-edge1-minimized-public-summary.timer
MUTATED=0
PUBLIC_TREE=/var/lib/bigbird-public-status
BOUNDARY_TREE=/var/lib/bigbird-edge1-boundary

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
backup_path() { local p=$1 n=$2; if [ -e "$p" ] || [ -L "$p" ]; then tar --numeric-owner -C "$(dirname "$p")" -czf "$BACKUP_DIR/$n.tar.gz" "$(basename "$p")"; else : >"$BACKUP_DIR/$n.absent"; fi; }
restore_path() { local p=$1 n=$2; rm -rf "$p"; if [ -f "$BACKUP_DIR/$n.tar.gz" ]; then tar --numeric-owner -C "$(dirname "$p")" -xzf "$BACKUP_DIR/$n.tar.gz"; fi; }
validate_protected_file() { local p=$1 max=$2 label=$3; [ -f "$p" ] || fail "$label is missing"; [ "$(stat -c %u "$p")" -eq 0 ] || fail "$label must be root-owned"; [ "$(stat -c %a "$p")" -le "$max" ] || fail "$label permissions are too broad"; }
render() {
  python3 - "$1" "$2" "$AUTH_USER_FILE" <<'PY'
import pathlib, sys
source, target, auth = map(pathlib.Path, sys.argv[1:])
if not auth.is_absolute() or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-' for c in str(auth)):
    raise SystemExit('authentication file path is unsafe')
target.write_text(source.read_text().replace('@@AUTH_USER_FILE@@', str(auth)))
PY
}
form_acceptance() {
  validate_protected_file "$ACCEPTANCE_FILE" 600 "acceptance credential file"
  local jar="$EVIDENCE_DIR/cookies.txt" response="$EVIDENCE_DIR/authenticated-root.html" code
  code=$(python3 - "$ACCEPTANCE_FILE" <<'PY' | curl -sS --max-time 20 -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' --header 'Content-Type: application/x-www-form-urlencoded' --data-binary @- "$PUBLIC_BASE/edge1-login/dologin.html"
import json, pathlib, sys, urllib.parse
value=json.loads(pathlib.Path(sys.argv[1]).read_text())
username=value.get('username') if isinstance(value, dict) else None
password=value.get('password') if isinstance(value, dict) else None
if not isinstance(username, str) or not username or not isinstance(password, str) or not password:
    raise SystemExit('acceptance credential JSON is incomplete')
sys.stdout.write(urllib.parse.urlencode({'httpd_username': username, 'httpd_password': password, 'httpd_location': '/edge1-ops/'}))
PY
  )
  case "$code" in 200|302|303) ;; *) fail "login handler returned HTTP $code";; esac
  code=$(curl -sS --max-time 20 -b "$jar" -D "$EVIDENCE_DIR/authenticated-root.headers" -o "$response" -w '%{http_code}' "$PUBLIC_BASE/edge1-ops/")
  [ "$code" = 200 ] || fail "authenticated detailed root returned HTTP $code"
  rm -f "$jar" "$response"
}
rollback() {
  local rc=$?
  if [ "$MUTATED" -eq 1 ]; then
    systemctl disable --now "$TIMER" >/dev/null 2>&1 || true
    rm -f "$CONF" "$ENABLED"
    [ -f "$BACKUP_DIR/apache.conf" ] && cp -a "$BACKUP_DIR/apache.conf" "$CONF"
    [ -L "$BACKUP_DIR/apache.enabled" ] && cp -a "$BACKUP_DIR/apache.enabled" "$ENABLED"
    for item in service timer exporter; do
      case "$item" in service) p=/etc/systemd/system/$SERVICE;; timer) p=/etc/systemd/system/$TIMER;; exporter) p=/usr/local/libexec/wwcx-security/edge1_public_status_exporter.py;; esac
      rm -f "$p"; [ -e "$BACKUP_DIR/$item" ] && cp -a "$BACKUP_DIR/$item" "$p"
    done
    restore_path "$PUBLIC_TREE" public-tree
    restore_path "$BOUNDARY_TREE" boundary-tree
    rm -f "$SESSION_KEYS"; [ -e "$BACKUP_DIR/session-keys" ] && cp -a "$BACKUP_DIR/session-keys" "$SESSION_KEYS"
    systemctl daemon-reload || true
    if [ "${TIMER_ENABLED_BEFORE:-disabled}" = enabled ]; then systemctl enable "$TIMER" >/dev/null 2>&1 || true; fi
    if [ "${TIMER_ACTIVE_BEFORE:-inactive}" = active ]; then systemctl start "$TIMER" >/dev/null 2>&1 || true; fi
    apache2ctl -t >/dev/null 2>&1 && systemctl reload apache2 >/dev/null 2>&1 || true
  fi
  printf 'rolled_back=true\nexit_code=%s\n' "$rc" >"$EVIDENCE_DIR/result.txt"
  rm -f "$EVIDENCE_DIR/cookies.txt" "$EVIDENCE_DIR/authenticated-root.html"
  find "$EVIDENCE_DIR" -type f ! -name manifest.sha256 -print0 | sort -z | xargs -0 -r sha256sum >"$EVIDENCE_DIR/manifest.sha256" || true
  exit "$rc"
}
trap rollback ERR INT TERM

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ "$(git -C "$REPO_ROOT" branch --show-current)" = main ] || fail "deployment requires main"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository must be clean"
[ -n "$AUTH_USER_FILE" ] || fail "EDGE1_AUTH_USER_FILE must point to an existing approved Apache password file"
[ -n "$ACCEPTANCE_FILE" ] || fail "EDGE1_AUTH_ACCEPTANCE_FILE must point to a root-protected acceptance file"
validate_protected_file "$AUTH_USER_FILE" 640 "authentication file"
validate_protected_file "$ACCEPTANCE_FILE" 600 "acceptance credential file"
install -d -o root -g root -m 0700 "$EVIDENCE_DIR" "$BACKUP_DIR"
python3 "$REPO_ROOT/tests/validate_edge1_security_completion.py" | tee "$EVIDENCE_DIR/repository-validation.txt"
apache2ctl -t >"$EVIDENCE_DIR/apache-before.txt" 2>&1
apache2ctl -M >"$EVIDENCE_DIR/apache-modules.txt" 2>&1
for module in auth_form_module session_module session_cookie_module session_crypto_module authn_file_module authz_user_module alias_module headers_module ratelimit_module setenvif_module; do grep -q " $module " "$EVIDENCE_DIR/apache-modules.txt" || fail "required Apache module is not enabled: $module"; done
ss -H -lntup 2>/dev/null | sort >"$EVIDENCE_DIR/listeners-before.txt" || true
curl -sS --max-time 20 -D "$EVIDENCE_DIR/public-before.headers" -o /dev/null "$PUBLIC_BASE/edge1-status/"
[ -e "$CONF" ] && cp -a "$CONF" "$BACKUP_DIR/apache.conf" || true
[ -L "$ENABLED" ] && cp -a "$ENABLED" "$BACKUP_DIR/apache.enabled" || true
for pair in "/etc/systemd/system/$SERVICE:service" "/etc/systemd/system/$TIMER:timer" "/usr/local/libexec/wwcx-security/edge1_public_status_exporter.py:exporter"; do p=${pair%%:*}; n=${pair##*:}; [ -e "$p" ] && cp -a "$p" "$BACKUP_DIR/$n" || true; done
backup_path "$PUBLIC_TREE" public-tree
backup_path "$BOUNDARY_TREE" boundary-tree
[ -e "$SESSION_KEYS" ] && cp -a "$SESSION_KEYS" "$BACKUP_DIR/session-keys" || : >"$BACKUP_DIR/session-keys.absent"
TIMER_ENABLED_BEFORE=$(systemctl is-enabled "$TIMER" 2>/dev/null || true)
TIMER_ACTIVE_BEFORE=$(systemctl is-active "$TIMER" 2>/dev/null || true)

install -d -o root -g root -m 0755 /usr/local/libexec/wwcx-security "$PUBLIC_TREE/www" "$BOUNDARY_TREE/login"
install -d -o root -g root -m 0700 /etc/wwcx/edge1-ops
install -o root -g root -m 0755 "$REPO_ROOT/server/edge1_public_status_exporter.py" /usr/local/libexec/wwcx-security/edge1_public_status_exporter.py
install -o root -g root -m 0644 "$REPO_ROOT/src/web/public-status/index.html" "$PUBLIC_TREE/www/index.html"
install -o root -g root -m 0644 "$REPO_ROOT/src/web/public-status/app.js" "$PUBLIC_TREE/www/app.js"
install -o root -g root -m 0644 "$REPO_ROOT/src/web/edge1-login/index.html" "$BOUNDARY_TREE/login/index.html"
install -o root -g root -m 0644 "$REPO_ROOT/src/web/edge1-login/style.css" "$BOUNDARY_TREE/login/style.css"
install -o root -g root -m 0644 "$REPO_ROOT/deploy/systemd/$SERVICE" "/etc/systemd/system/$SERVICE"
install -o root -g root -m 0644 "$REPO_ROOT/deploy/systemd/$TIMER" "/etc/systemd/system/$TIMER"
if [ ! -s "$SESSION_KEYS" ]; then umask 077; openssl rand -hex 32 >"$SESSION_KEYS"; fi
chown root:root "$SESSION_KEYS"; chmod 0600 "$SESSION_KEYS"
render "$REPO_ROOT/deploy/apache/edge1-security-boundary-stage.conf.in" "$CONF"
ln -sfn ../conf-available/edge1-security-boundary.conf "$ENABLED"
MUTATED=1
systemctl daemon-reload
systemctl start "$SERVICE"
python3 - "$REPO_ROOT/schemas/wwcx-edge1-public-status-v1.schema.json" "$PUBLIC_TREE/www/status.json" "$EVIDENCE_DIR/minimized-summary.json" <<'PY'
import json, pathlib, sys
schema=json.loads(pathlib.Path(sys.argv[1]).read_text())
value=json.loads(pathlib.Path(sys.argv[2]).read_text())
expected={'schema_version','generated_at','overall_state','component_category','maintenance_notice','read_only','traffic_controls_changed'}
if set(value) != expected or value.get('schema_version') != schema['properties']['schema_version']['const']:
    raise SystemExit('minimized summary contract mismatch')
pathlib.Path(sys.argv[3]).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
PY
systemctl enable --now "$TIMER"
apache2ctl -t >"$EVIDENCE_DIR/apache-stage-test.txt" 2>&1
systemctl reload apache2
anonymous=$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "$PUBLIC_BASE/edge1-ops/")
case "$anonymous" in 302|303|401|403) ;; *) fail "anonymous detailed route did not fail closed: HTTP $anonymous";; esac
login=$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "$PUBLIC_BASE/edge1-login/")
[ "$login" = 200 ] || fail "login page returned HTTP $login"
form_acceptance
curl -sS --max-time 20 -D "$EVIDENCE_DIR/public-after.headers" -o /dev/null "$PUBLIC_BASE/edge1-status/"
ss -H -lntup 2>/dev/null | sort >"$EVIDENCE_DIR/listeners-after.txt" || true
cmp -s "$EVIDENCE_DIR/listeners-before.txt" "$EVIDENCE_DIR/listeners-after.txt" || fail "listener state changed"
printf 'rolled_back=false\nstatus=authenticated-stage-accepted\n' >"$EVIDENCE_DIR/result.txt"
find "$EVIDENCE_DIR" -type f ! -name manifest.sha256 -print0 | sort -z | xargs -0 sha256sum >"$EVIDENCE_DIR/manifest.sha256"
trap - ERR INT TERM
printf '%s\n' "$EVIDENCE_DIR"
