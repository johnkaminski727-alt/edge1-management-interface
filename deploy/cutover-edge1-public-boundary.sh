#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/edge1-public-boundary-cutover}
AUTH_USER_FILE=${EDGE1_AUTH_USER_FILE:-}
ACCEPTANCE_FILE=${EDGE1_AUTH_ACCEPTANCE_FILE:-}
PUBLIC_BASE=${EDGE1_PUBLIC_BASE_URL:-https://edge1.ww.cx}
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
CONF=/etc/apache2/conf-available/edge1-security-boundary.conf
STAGE_COPY="$EVIDENCE_DIR/stage.conf"
CUTOVER_COPY="$EVIDENCE_DIR/cutover.conf"
MUTATED=0

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
protected() { [ -f "$1" ] && [ "$(stat -c %u "$1")" -eq 0 ] && [ "$(stat -c %a "$1")" -le "$2" ]; }
render() {
  python3 - "$1" "$2" "$AUTH_USER_FILE" <<'PY'
import pathlib, sys
source, target, auth = map(pathlib.Path, sys.argv[1:])
if not auth.is_absolute() or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-' for c in str(auth)):
    raise SystemExit('unsafe authentication file path')
target.write_text(source.read_text().replace('@@AUTH_USER_FILE@@', str(auth)))
PY
}
login_check() {
  local jar="$EVIDENCE_DIR/cookies.txt" code
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
  case "$code" in 200|302|303) ;; *) fail "login handler failed with HTTP $code";; esac
  code=$(curl -sS --max-time 20 -b "$jar" -o /dev/null -w '%{http_code}' "$PUBLIC_BASE/edge1-ops/")
  [ "$code" = 200 ] || fail "authenticated detailed root returned HTTP $code"
  for path in security-operations.json operations-inventory.json operations-network.json; do
    code=$(curl -sS --max-time 20 -b "$jar" -o /dev/null -w '%{http_code}' "$PUBLIC_BASE/edge1-ops/$path")
    [ "$code" = 200 ] || fail "authenticated detailed route $path returned HTTP $code"
  done
  rm -f "$jar"
}
rollback() {
  local rc=$?
  if [ "$MUTATED" -eq 1 ]; then
    install -o root -g root -m 0644 "$STAGE_COPY" "$CONF"
    apache2ctl -t >/dev/null 2>&1 && systemctl reload apache2 >/dev/null 2>&1 || true
  fi
  printf 'rolled_back=true\nexit_code=%s\n' "$rc" >"$EVIDENCE_DIR/result.txt"
  rm -f "$EVIDENCE_DIR/cookies.txt"
  find "$EVIDENCE_DIR" -type f ! -name manifest.sha256 -print0 | sort -z | xargs -0 -r sha256sum >"$EVIDENCE_DIR/manifest.sha256" || true
  exit "$rc"
}
trap rollback ERR INT TERM

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ "$(git -C "$REPO_ROOT" branch --show-current)" = main ] || fail "cutover requires main"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository must be clean"
[ -n "$AUTH_USER_FILE" ] && protected "$AUTH_USER_FILE" 640 || fail "approved root-owned authentication file is required"
[ -n "$ACCEPTANCE_FILE" ] && protected "$ACCEPTANCE_FILE" 600 || fail "root-protected acceptance credential file is required"
[ -f "$CONF" ] || fail "authenticated stage is not installed"
grep -q 'Alias "/edge1-ops/"' "$CONF" || fail "authenticated detailed alias is not staged"
! grep -q 'Alias "/edge1-status/" "/var/lib/bigbird-public-status' "$CONF" || fail "public cutover is already active"
systemctl is-active --quiet wwcx-edge1-minimized-public-summary.timer || fail "minimized summary timer is not active"
systemctl start wwcx-edge1-minimized-public-summary.service
install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
cp -a "$CONF" "$STAGE_COPY"
render "$REPO_ROOT/deploy/apache/edge1-security-boundary-cutover.conf.in" "$CUTOVER_COPY"
login_check
# Authentication succeeds before any anonymous route is withdrawn.

find "$STATUS_ROOT" -xdev -maxdepth 6 -type f -printf '%m\t%u\t%g\t%s\t%p\n' | sort >"$EVIDENCE_DIR/detailed-inventory-before.tsv"
find "$STATUS_ROOT" -xdev -maxdepth 6 -type f -print0 | sort -z | xargs -0 sha256sum >"$EVIDENCE_DIR/detailed-sha256-before.txt"
tar --one-file-system --numeric-owner -C "$(dirname "$STATUS_ROOT")" -czf "$EVIDENCE_DIR/detailed-public-archive.tar.gz" "$(basename "$STATUS_ROOT")"
chmod 0600 "$EVIDENCE_DIR/detailed-public-archive.tar.gz"
sha256sum "$EVIDENCE_DIR/detailed-public-archive.tar.gz" >"$EVIDENCE_DIR/detailed-public-archive.sha256"
ss -H -lntup 2>/dev/null | sort >"$EVIDENCE_DIR/listeners-before.txt" || true
install -o root -g root -m 0644 "$CUTOVER_COPY" "$CONF"
MUTATED=1
apache2ctl -t >"$EVIDENCE_DIR/apache-cutover-test.txt" 2>&1
systemctl reload apache2

code=$(curl -sS --max-time 20 -D "$EVIDENCE_DIR/public-root.headers" -o "$EVIDENCE_DIR/public-root.html" -w '%{http_code}' "$PUBLIC_BASE/edge1-status/")
[ "$code" = 200 ] || fail "minimized public root returned HTTP $code"
code=$(curl -sS --max-time 20 -D "$EVIDENCE_DIR/public-status.headers" -o "$EVIDENCE_DIR/public-status.json" -w '%{http_code}' "$PUBLIC_BASE/edge1-status/public/status.json")
[ "$code" = 200 ] || fail "minimized public status returned HTTP $code"
python3 - "$EVIDENCE_DIR/public-status.json" <<'PY'
import json, pathlib, sys
value=json.loads(pathlib.Path(sys.argv[1]).read_text())
expected={'schema_version','generated_at','overall_state','component_category','maintenance_notice','read_only','traffic_controls_changed'}
if set(value) != expected or value.get('schema_version') != 'wwcx.edge1-public-status.v1':
    raise SystemExit('public summary is not the exact minimized contract')
encoded=json.dumps(value).lower()
for token in ('hostname','kernel','service_name','source_address','destination_address','source_port','destination_port','flow_id','event_id','incident','report_filename','raw_error'):
    if token in encoded: raise SystemExit(f'forbidden public token: {token}')
PY
for path in security/ security/correlation.html security-operations.json security-correlation.json network-defense/data/network-defense.json operations-inventory.json operations-network.json operations-version.json operations-changes.json operations-incidents.json operations-incident-history.json reports/; do
  code=$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "$PUBLIC_BASE/edge1-status/$path")
  [ "$code" = 404 ] || fail "superseded anonymous route $path returned HTTP $code instead of 404"
done
anonymous=$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "$PUBLIC_BASE/edge1-ops/")
case "$anonymous" in 302|303|401|403) ;; *) fail "anonymous detailed route returned HTTP $anonymous";; esac
login_check
for header_file in "$EVIDENCE_DIR/public-root.headers" "$EVIDENCE_DIR/public-status.headers"; do
  grep -qi '^Cache-Control:.*no-store' "$header_file" || fail "no-store header missing"
  grep -qi '^Referrer-Policy:.*no-referrer' "$header_file" || fail "referrer policy missing"
  grep -qi '^X-Content-Type-Options:.*nosniff' "$header_file" || fail "nosniff header missing"
  ! grep -qi '^Access-Control-Allow-Origin:' "$header_file" || fail "CORS header must be absent"
done
ss -H -lntup 2>/dev/null | sort >"$EVIDENCE_DIR/listeners-after.txt" || true
cmp -s "$EVIDENCE_DIR/listeners-before.txt" "$EVIDENCE_DIR/listeners-after.txt" || fail "listener state changed"
printf 'rolled_back=false\nstatus=cutover-accepted\ndetailed_artifacts_deleted=false\ndetailed_public_routes_withdrawn=true\n' >"$EVIDENCE_DIR/result.txt"
find "$EVIDENCE_DIR" -type f ! -name manifest.sha256 ! -name cookies.txt -print0 | sort -z | xargs -0 sha256sum >"$EVIDENCE_DIR/manifest.sha256"
trap - ERR INT TERM
printf '%s\n' "$EVIDENCE_DIR"
