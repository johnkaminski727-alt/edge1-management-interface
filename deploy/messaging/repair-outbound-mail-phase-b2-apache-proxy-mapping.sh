#!/bin/sh
set -eu

umask 077

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
EXPECTED_COMMIT=${EXPECTED_COMMIT:-}
ACTION=${ACTION:-audit}
APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED=${APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED:-no}
ROLLBACK_EVIDENCE=${ROLLBACK_EVIDENCE:-}

APACHE_SERVICE=apache2.service
GATEWAY_SERVICE=wwcx-outbound-mail-gateway.service
ACTIVE_VHOST=/etc/apache2/sites-enabled/edge1.ww.cx.conf
VHOST_TARGET=/etc/apache2/sites-available/edge1.ww.cx.conf
FRAGMENT_PATH=/etc/apache2/wwcx-outbound-mail-preparation-api.conf
TEMPLATE=$REPO_ROOT/deploy/messaging/outbound-mail-preparation-api-apache.conf.example
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/outbound-mail-apache-proxy-mapping-repair
ROLLBACK_ROOT=/var/lib/wwcx-deployment-evidence/outbound-mail-apache-proxy-mapping-rollback
INCLUDE_LINE='    IncludeOptional /etc/apache2/wwcx-outbound-mail-preparation-api.conf'

EVIDENCE_DIR=
MUTATION_STARTED=false
REPAIR_ACCEPTED=false
ROLLBACK_IN_PROGRESS=false

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

record() {
  printf '%s=%s\n' "$1" "$2" >> "$EVIDENCE_DIR/summary.txt"
}

file_sha256() {
  sha256sum "$1" | awk '{print $1}'
}

write_manifest() {
  (
    cd "$EVIDENCE_DIR"
    find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
  )
  chmod -R go-rwx "$EVIDENCE_DIR"
}

verify_repository() {
  [ -n "$EXPECTED_COMMIT" ] || fail "EXPECTED_COMMIT is required"
  printf '%s\n' "$EXPECTED_COMMIT" | grep -Eq '^[0-9a-f]{40}$' || fail "EXPECTED_COMMIT must be a full lowercase commit SHA"
  [ -d "$REPO_ROOT/.git" ] || fail "repository not found at $REPO_ROOT"
  [ "$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)" = main ] || fail "repository branch is not main"
  [ "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$EXPECTED_COMMIT" ] || fail "repository HEAD does not match EXPECTED_COMMIT"
  [ -z "$(GIT_OPTIONAL_LOCKS=0 git -C "$REPO_ROOT" status --porcelain --untracked-files=all)" ] || fail "repository is not clean"
  [ -f "$TEMPLATE" ] || fail "reviewed Apache fragment template is absent"
}

probe_common_state() {
  systemctl is-active --quiet "$APACHE_SERVICE" || fail "$APACHE_SERVICE is not active"
  systemctl is-active --quiet "$GATEWAY_SERVICE" || fail "$GATEWAY_SERVICE is not active"
  apache2ctl configtest >/dev/null 2>&1 || fail "Apache configuration is invalid"

  [ -L "$ACTIVE_VHOST" ] || fail "active Edge1 vhost is not an enabled-site symlink"
  [ "$(readlink -f "$ACTIVE_VHOST" || true)" = "$VHOST_TARGET" ] || fail "active Edge1 vhost resolves unexpectedly"
  [ -f "$VHOST_TARGET" ] || fail "active Edge1 vhost target is absent"
  [ -f "$FRAGMENT_PATH" ] && [ ! -L "$FRAGMENT_PATH" ] || fail "live preparation fragment is absent or is a symlink"
  [ "$(stat -c %U:%G "$FRAGMENT_PATH")" = root:root ] || fail "live preparation fragment is not root-owned"
  [ "$(stat -c %a "$FRAGMENT_PATH")" = 644 ] || fail "live preparation fragment mode is not 0644"
  [ "$(grep -Fxc "$INCLUDE_LINE" "$VHOST_TARGET")" -eq 1 ] || fail "approved include line is not present exactly once"

  listener=$(ss -lnt 2>/dev/null | awk 'NR > 1 {print $4}' | grep -E ':8104$' || true)
  [ "$listener" = '127.0.0.1:8104' ] || fail "gateway port 8104 is not isolated to IPv4 loopback"

  direct_status=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/api/v1/status || true)
  direct_send=$(curl -sS --max-time 5 -H 'Content-Type: application/json' -d '{}' -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/send || true)
  local_status=$(curl -sS --max-time 10 --resolve edge1.ww.cx:443:127.0.0.1 -o /dev/null -w '%{http_code}' https://edge1.ww.cx/outbound-mail/api/v1/status || true)
  local_prepare=$(curl -sS --max-time 10 --resolve edge1.ww.cx:443:127.0.0.1 -H 'Content-Type: application/json' -d '{}' -o /dev/null -w '%{http_code}' https://edge1.ww.cx/outbound-mail/api/v1/prepare || true)
  local_send=$(curl -sS --max-time 10 --resolve edge1.ww.cx:443:127.0.0.1 -H 'Content-Type: application/json' -d '{}' -o /dev/null -w '%{http_code}' https://edge1.ww.cx/outbound-mail/send || true)
  local_health=$(curl -sS --max-time 10 --resolve edge1.ww.cx:443:127.0.0.1 -o /dev/null -w '%{http_code}' https://edge1.ww.cx/outbound-mail/healthz || true)

  [ "$direct_status" = 401 ] || fail "direct unsigned preparation status is not HTTP 401"
  [ "$direct_send" = 403 ] || fail "direct send endpoint is not HTTP 403"
  [ "$local_status" = 403 ] || fail "unapproved local source is not denied on status"
  [ "$local_prepare" = 403 ] || fail "unapproved local source is not denied on prepare"
  [ "$local_send" = 404 ] || fail "public TLS send route is unexpectedly exposed"
  [ "$local_health" = 404 ] || fail "public TLS health route is unexpectedly exposed"
}

verify_legacy_fragment() {
  [ "$(grep -c '^    ProxyPass "http://127.0.0.1:8104/outbound-mail/api/v1/' "$FRAGMENT_PATH" || true)" -eq 2 ] || fail "live fragment does not contain exactly two legacy ProxyPass mappings"
  [ "$(grep -c '^    ProxyPassMatch ' "$FRAGMENT_PATH" || true)" -eq 0 ] || fail "live fragment is not in the expected legacy mapping state"
  [ "$(grep -c '^<LocationMatch "\^/outbound-mail/api/v1/status\$">$' "$FRAGMENT_PATH" || true)" -eq 1 ] || fail "status LocationMatch drifted"
  [ "$(grep -c '^<LocationMatch "\^/outbound-mail/api/v1/prepare\$">$' "$FRAGMENT_PATH" || true)" -eq 1 ] || fail "prepare LocationMatch drifted"
  [ "$(grep -Fc 'Require ip 162.0.217.71/32' "$FRAGMENT_PATH")" -eq 2 ] || fail "approved source restrictions drifted"
  ! grep -Fq '/outbound-mail/send' "$FRAGMENT_PATH" || fail "live fragment unexpectedly contains a send route"
}

verify_repaired_fragment() {
  file=$1
  [ "$(grep -c '^    ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/' "$file" || true)" -eq 2 ] || fail "candidate does not contain exactly two ProxyPassMatch mappings"
  [ "$(grep -c '^    ProxyPass "' "$file" || true)" -eq 0 ] || fail "candidate still contains legacy ProxyPass mappings"
  [ "$(grep -Fc 'Require ip 162.0.217.71/32' "$file")" -eq 2 ] || fail "candidate source restrictions drifted"
  ! grep -Fq '/outbound-mail/send' "$file" || fail "candidate unexpectedly contains a send route"
}

render_candidate() {
  python3 - "$FRAGMENT_PATH" "$EVIDENCE_DIR/fragment.candidate.conf" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
needle = '    ProxyPass "http://127.0.0.1:8104/outbound-mail/api/v1/'
replacement = '    ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/'
if source.count(needle) != 2:
    raise SystemExit("expected exactly two legacy ProxyPass mappings")
candidate = source.replace(needle, replacement)
if candidate.count(replacement) != 2:
    raise SystemExit("candidate does not contain exactly two ProxyPassMatch mappings")
if candidate.replace(replacement, needle) != source:
    raise SystemExit("candidate changes more than the two proxy directive names")
pathlib.Path(sys.argv[2]).write_text(candidate, encoding="utf-8")
PY
  verify_repaired_fragment "$EVIDENCE_DIR/fragment.candidate.conf"
}

restore_current_evidence() {
  [ -n "$EVIDENCE_DIR" ] || return 1
  [ -f "$EVIDENCE_DIR/fragment.before.conf" ] || return 1
  cp -a -- "$EVIDENCE_DIR/fragment.before.conf" "$FRAGMENT_PATH"
  apache2ctl configtest > "$EVIDENCE_DIR/rollback-configtest.txt" 2>&1
  systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/rollback-reload.txt" 2>&1
  systemctl is-active --quiet "$APACHE_SERVICE"
}

rollback_if_needed() {
  if [ "$MUTATION_STARTED" = true ] && [ "$REPAIR_ACCEPTED" != true ] && [ "$ROLLBACK_IN_PROGRESS" != true ]; then
    ROLLBACK_IN_PROGRESS=true
    echo "Apache proxy-mapping repair failed; restoring the previous fragment." >&2
    if restore_current_evidence; then
      printf 'automatic_rollback=pass\nrollback_state=restored\n' >> "$EVIDENCE_DIR/summary.txt"
    else
      printf 'automatic_rollback=failed\nrollback_state=uncertain\n' >> "$EVIDENCE_DIR/summary.txt"
      echo "WARNING: automatic rollback failed; inspect $EVIDENCE_DIR before further action." >&2
    fi
    write_manifest || true
  fi
}

on_exit() {
  rc=$?
  trap - EXIT HUP INT TERM
  rollback_if_needed
  exit "$rc"
}

manual_rollback() {
  [ -n "$ROLLBACK_EVIDENCE" ] || fail "ROLLBACK_EVIDENCE is required for ACTION=rollback"
  [ -d "$ROLLBACK_EVIDENCE" ] && [ ! -L "$ROLLBACK_EVIDENCE" ] || fail "rollback evidence is absent or a symlink"
  [ "$(stat -c %U:%G "$ROLLBACK_EVIDENCE")" = root:root ] || fail "rollback evidence is not root-owned"
  [ "$(stat -c %a "$ROLLBACK_EVIDENCE")" = 700 ] || fail "rollback evidence mode is not 0700"
  (
    cd "$ROLLBACK_EVIDENCE"
    sha256sum -c SHA256SUMS >/dev/null
  ) || fail "rollback evidence manifest verification failed"
  grep -Fqx 'readiness_state=awaiting_business159_source_acceptance' "$ROLLBACK_EVIDENCE/summary.txt" || fail "rollback source is not an accepted repair"
  [ -f "$ROLLBACK_EVIDENCE/fragment.before.conf" ] || fail "rollback source lacks the original fragment"
  [ -f "$ROLLBACK_EVIDENCE/fragment.after.conf" ] || fail "rollback source lacks the repaired fragment"
  [ "$(file_sha256 "$FRAGMENT_PATH")" = "$(file_sha256 "$ROLLBACK_EVIDENCE/fragment.after.conf")" ] || fail "live fragment drifted after repair"

  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  EVIDENCE_DIR=$ROLLBACK_ROOT/$stamp
  install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
  : > "$EVIDENCE_DIR/summary.txt"
  record captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  record host "$EXPECTED_HOST"
  record principal root
  record source_repair_evidence "$ROLLBACK_EVIDENCE"
  cp -a -- "$FRAGMENT_PATH" "$EVIDENCE_DIR/fragment.before-rollback.conf"
  cp -a -- "$ROLLBACK_EVIDENCE/fragment.before.conf" "$FRAGMENT_PATH"
  apache2ctl configtest > "$EVIDENCE_DIR/configtest.txt" 2>&1
  systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/apache-reload.txt" 2>&1
  systemctl is-active --quiet "$APACHE_SERVICE" || fail "Apache is not active after rollback"
  verify_legacy_fragment
  probe_common_state
  record rollback_state restored
  record external_delivery_enabled no
  record message_sent no
  write_manifest
  echo "Apache proxy-mapping repair rolled back successfully."
  echo "Evidence: $EVIDENCE_DIR"
}

case "$ACTION" in
  audit|install|rollback) ;;
  *) fail "ACTION must be audit, install, or rollback" ;;
esac

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ "$(hostname -f 2>/dev/null || hostname)" = "$EXPECTED_HOST" ] || fail "unexpected host"
verify_repository

if [ "$ACTION" = rollback ]; then
  manual_rollback
  exit 0
fi

probe_common_state
verify_legacy_fragment

stamp=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR=$EVIDENCE_ROOT/$stamp
install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
: > "$EVIDENCE_DIR/summary.txt"
: > "$EVIDENCE_DIR/failures.txt"
record captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
record host "$EXPECTED_HOST"
record principal root
record action "$ACTION"
record repository "$REPO_ROOT"
record branch main
record head_commit "$EXPECTED_COMMIT"
record fragment_path "$FRAGMENT_PATH"
record approved_source 162.0.217.71/32
record observed_business159_status_http 404
record expected_business159_status_http 401
record hmac_secret_read no
record provider_or_sender_enabled no
record external_delivery_enabled no
record message_prepared no
record message_sent no
cp -a -- "$FRAGMENT_PATH" "$EVIDENCE_DIR/fragment.before.conf"
render_candidate
diff -u "$EVIDENCE_DIR/fragment.before.conf" "$EVIDENCE_DIR/fragment.candidate.conf" > "$EVIDENCE_DIR/fragment.diff" || true

if [ "$ACTION" = audit ]; then
  record proxy_mapping_defect_confirmed yes
  record proposed_directive_change_count 2
  record apache_reloaded no
  record readiness_state ready_for_explicit_apache_proxy_mapping_repair_authorization
  record failures 0
  write_manifest
  echo "Apache proxy-mapping repair audit completed without mutation."
  echo "readiness_state=ready_for_explicit_apache_proxy_mapping_repair_authorization"
  echo "Evidence: $EVIDENCE_DIR"
  exit 0
fi

[ "$APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED" = yes ] || fail "install requires APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED=yes"
trap on_exit EXIT HUP INT TERM
install -o root -g root -m 0644 "$EVIDENCE_DIR/fragment.candidate.conf" "$FRAGMENT_PATH"
MUTATION_STARTED=true
apache2ctl configtest > "$EVIDENCE_DIR/configtest.txt" 2>&1
systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/apache-reload.txt" 2>&1
systemctl is-active --quiet "$APACHE_SERVICE" || fail "Apache is not active after repair reload"
verify_repaired_fragment "$FRAGMENT_PATH"
probe_common_state
cp -a -- "$FRAGMENT_PATH" "$EVIDENCE_DIR/fragment.after.conf"
record proxy_mapping_repaired yes
record proposed_directive_change_count 2
record apache_reloaded yes
record approved_source_external_canary pending
record readiness_state awaiting_business159_source_acceptance
record failures 0
write_manifest
REPAIR_ACCEPTED=true
trap - EXIT HUP INT TERM

echo "Apache proxy-mapping repair installed and locally verified."
echo "Business159 external source acceptance must be rerun before credential installation."
echo "No credential, provider, sender, delivery, or message state was enabled."
echo "Evidence: $EVIDENCE_DIR"
