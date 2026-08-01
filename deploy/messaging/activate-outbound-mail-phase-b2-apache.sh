#!/bin/sh
set -eu

umask 077

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
EXPECTED_COMMIT=${EXPECTED_COMMIT:-}
APPROVED_ACTIVATION_COMMIT=${APPROVED_ACTIVATION_COMMIT:-}
PROPOSAL_PACKAGE_COMMIT=${PROPOSAL_PACKAGE_COMMIT:-105ea0f2dd79a3bbc5a09c5c7c7ed49eab5a0e0d}
PROPOSAL_EVIDENCE=${PROPOSAL_EVIDENCE:-/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal/20260801T210934Z}
ACTION=${ACTION:-install}
ROLLBACK_EVIDENCE=${ROLLBACK_EVIDENCE:-}

SERVICE_NAME=wwcx-outbound-mail-gateway.service
APACHE_SERVICE=apache2.service
PROPOSED_HOSTNAME=edge1.ww.cx
PROPOSED_CLIENT_CIDR=162.0.217.71/32
CERTIFICATE_FULLCHAIN_PATH=/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
CERTIFICATE_PRIVATE_KEY_PATH=/etc/letsencrypt/live/edge1.ww.cx/privkey.pem
ACTIVE_VHOST=/etc/apache2/sites-enabled/edge1.ww.cx.conf
FRAGMENT_PATH=/etc/apache2/wwcx-outbound-mail-preparation-api.conf
TEMPLATE=$REPO_ROOT/deploy/messaging/outbound-mail-preparation-api-apache.conf.example
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-activation
ROLLBACK_ROOT=/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-rollback
INCLUDE_LINE="    IncludeOptional $FRAGMENT_PATH"

EVIDENCE_DIR=
VHOST_TARGET=
MUTATION_STARTED=false
ACTIVATION_ACCEPTED=false
ROLLBACK_IN_PROGRESS=false

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

record() {
  printf '%s=%s\n' "$1" "$2" >> "$EVIDENCE_DIR/summary.txt"
}

latest_file_sha256() {
  sha256sum "$1" | awk '{print $1}'
}

verify_repository() {
  [ -n "$EXPECTED_COMMIT" ] || fail "EXPECTED_COMMIT is required"
  [ -n "$APPROVED_ACTIVATION_COMMIT" ] || fail "APPROVED_ACTIVATION_COMMIT is required"
  printf '%s\n' "$APPROVED_ACTIVATION_COMMIT" | grep -Eq '^[0-9a-f]{40}$' || fail "APPROVED_ACTIVATION_COMMIT must be a full lowercase commit SHA"
  [ -d "$REPO_ROOT/.git" ] || fail "repository not found at $REPO_ROOT"
  [ "$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)" = main ] || fail "repository branch is not main"
  [ "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$EXPECTED_COMMIT" ] || fail "repository HEAD does not match EXPECTED_COMMIT"
  [ -z "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=all)" ] || fail "repository is not clean"
  git -C "$REPO_ROOT" merge-base --is-ancestor "$PROPOSAL_PACKAGE_COMMIT" HEAD || fail "proposal package commit is not an ancestor of HEAD"
  git -C "$REPO_ROOT" cat-file -e "${APPROVED_ACTIVATION_COMMIT}^{commit}" || fail "approved activation commit is not present"
  git -C "$REPO_ROOT" merge-base --is-ancestor "$APPROVED_ACTIVATION_COMMIT" HEAD || fail "approved activation commit is not an ancestor of HEAD"

  protected_paths='deploy/messaging/activate-outbound-mail-phase-b2-apache.sh
  deploy/messaging/outbound-mail-preparation-api-apache.conf.example
  tools/messaging/outbound_mail_phase_b2_apache_proposal_audit.sh
  docs/messaging-operations/outbound-mail-phase-b2-apache-proposal-20260801.md
  docs/messaging-operations/outbound-mail-phase-b2-apache-activation-20260801.md
  server/outbound_mail_gateway.py
  server/outbound_mail_gateway_server.py
  server/outbound_mail_preparation_auth.py
  config/messaging/outbound-mail-gateway.json
  config/messaging/outbound-mail-policy.json
  config/messaging/mail-identities.json'
  if ! git -C "$REPO_ROOT" diff --quiet "$APPROVED_ACTIVATION_COMMIT"..HEAD -- $protected_paths; then
    git -C "$REPO_ROOT" diff --name-only "$APPROVED_ACTIVATION_COMMIT"..HEAD -- $protected_paths >&2 || true
    fail "protected Phase B2 files changed after the approved activation baseline"
  fi
}

verify_common_host_state() {
  [ "$(id -u)" -eq 0 ] || fail "run as root"
  [ "$(hostname -f 2>/dev/null || hostname)" = "$EXPECTED_HOST" ] || fail "unexpected host"
  verify_repository

  systemctl is-active --quiet "$SERVICE_NAME" || fail "$SERVICE_NAME is not active"
  systemctl is-enabled --quiet "$SERVICE_NAME" || fail "$SERVICE_NAME is not enabled"
  [ "$(systemctl show "$SERVICE_NAME" -p User --value)" = wwcx-mail-gateway ] || fail "unexpected gateway service principal"
  systemctl is-active --quiet "$APACHE_SERVICE" || fail "$APACHE_SERVICE is not active"
  systemctl is-enabled --quiet "$APACHE_SERVICE" || fail "$APACHE_SERVICE is not enabled"

  port_addresses=$(ss -lnt 2>/dev/null | awk 'NR > 1 {print $4}' | grep -E ':8104$' || true)
  [ "$port_addresses" = '127.0.0.1:8104' ] || fail "gateway port 8104 is not isolated to IPv4 loopback"

  direct_health=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/healthz || true)
  direct_unsigned=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/api/v1/status || true)
  direct_send=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8104/outbound-mail/send || true)
  [ "$direct_health" = 200 ] || fail "direct gateway health is not HTTP 200"
  [ "$direct_unsigned" = 401 ] || fail "direct unsigned preparation status is not HTTP 401"
  [ "$direct_send" = 403 ] || fail "direct send endpoint is not HTTP 403"

  [ -L "$ACTIVE_VHOST" ] || fail "active edge1 vhost is not an enabled-site symlink"
  VHOST_TARGET=$(readlink -f "$ACTIVE_VHOST" || true)
  [ "$VHOST_TARGET" = /etc/apache2/sites-available/edge1.ww.cx.conf ] || fail "active vhost resolves to an unexpected target"
  [ -f "$VHOST_TARGET" ] || fail "active vhost target is absent"
  [ -f "$TEMPLATE" ] || fail "reviewed Apache fragment template is absent"
}

verify_proposal_evidence() {
  [ -d "$PROPOSAL_EVIDENCE" ] || fail "accepted proposal evidence directory is missing"
  [ ! -L "$PROPOSAL_EVIDENCE" ] || fail "proposal evidence directory must not be a symlink"
  [ "$(stat -c %u "$PROPOSAL_EVIDENCE")" -eq 0 ] || fail "proposal evidence directory must be root-owned"
  [ "$(stat -c %a "$PROPOSAL_EVIDENCE")" = 700 ] || fail "proposal evidence directory must have mode 0700"
  (
    cd "$PROPOSAL_EVIDENCE"
    sha256sum -c SHA256SUMS >/dev/null
  ) || fail "proposal evidence hash verification failed"
  [ ! -s "$PROPOSAL_EVIDENCE/failures.txt" ] || fail "proposal evidence contains failures"

  required_lines='host=edge1.ww.cx
principal=root
repository=/opt/edge1-management-interface
branch=main
proposed_hostname=edge1.ww.cx
proposed_client_cidr=162.0.217.71/32
certificate_fullchain_path=/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
certificate_private_key_path=/etc/letsencrypt/live/edge1.ww.cx/privkey.pem
active_vhost=/etc/apache2/sites-enabled/edge1.ww.cx.conf
active_vhost_resolved=/etc/apache2/sites-available/edge1.ww.cx.conf
health_http=200
status_http=200
unsigned_api_status_http=401
send_probe_http=403
fullchain_reference_count=1
private_key_reference_count=1
certificate_private_key_contents_read=no
certificate_key_pair_match_deferred_to_install=yes
hmac_secret_read=no
proxy_config_installed=no
proxy_service_reloaded=no
certificate_generated=no
dns_modified=no
firewall_modified=no
public_listener_added=no
website_bridge_enabled=no
provider_or_sender_enabled=no
external_delivery_enabled=no
message_sent=no
readiness_state=ready_for_explicit_b2_apache_authorization
failures=0'
  printf '%s\n' "$required_lines" | while IFS= read -r line; do
    grep -Fqx "$line" "$PROPOSAL_EVIDENCE/summary.txt" || fail "proposal evidence is missing required fact: $line"
  done

  proposal_head=$(awk -F= '$1 == "head_commit" {print $2}' "$PROPOSAL_EVIDENCE/summary.txt")
  [ "$proposal_head" = d89cbb06d5ecd171e67c1a281beb58ef16a1f24c ] || fail "proposal evidence was not captured at the accepted repository HEAD"
}

render_candidate() {
  python3 - "$TEMPLATE" "$EVIDENCE_DIR/candidate-apache-fragment.conf" <<'PY'
import pathlib
import sys

template = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
out = pathlib.Path(sys.argv[2])
values = {
    "PREPARATION_API_HOSTNAME": "edge1.ww.cx",
    "PREPARATION_CLIENT_CIDR": "162.0.217.71/32",
    "CERTIFICATE_FULLCHAIN_PATH": "/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem",
    "CERTIFICATE_PRIVATE_KEY_PATH": "/etc/letsencrypt/live/edge1.ww.cx/privkey.pem",
}
for key, value in values.items():
    template = template.replace(key, value)
for key in values:
    if key in template:
        raise SystemExit(f"candidate contains unreplaced placeholder: {key}")
if "/outbound-mail/send" in template:
    raise SystemExit("candidate contains an unauthorized send route")
if template.count('Require ip 162.0.217.71/32') != 2:
    raise SystemExit("candidate does not contain exactly two approved source restrictions")
out.write_text(template, encoding="utf-8")
PY
}

patch_vhost() {
  python3 - "$VHOST_TARGET" "$INCLUDE_LINE" "$CERTIFICATE_FULLCHAIN_PATH" "$CERTIFICATE_PRIVATE_KEY_PATH" <<'PY'
import os
import pathlib
import re
import stat
import sys

path = pathlib.Path(sys.argv[1])
include_line = sys.argv[2]
fullchain = sys.argv[3]
private_key = sys.argv[4]
text = path.read_text(encoding="utf-8")
if include_line.strip() in text:
    raise SystemExit("approved include line already exists")
if "outbound-mail/api/v1" in text:
    raise SystemExit("active vhost already contains an outbound-mail preparation route")

lines = text.splitlines(keepends=True)
blocks = []
start = None
for index, line in enumerate(lines):
    stripped = line.strip()
    if re.match(r"^<VirtualHost\b", stripped, re.IGNORECASE):
        if start is not None:
            raise SystemExit("nested VirtualHost blocks are not supported")
        start = index
    elif re.match(r"^</VirtualHost>$", stripped, re.IGNORECASE):
        if start is None:
            raise SystemExit("unmatched VirtualHost closing tag")
        blocks.append((start, index))
        start = None
if start is not None:
    raise SystemExit("unclosed VirtualHost block")

matches = []
for block_start, block_end in blocks:
    block = "".join(lines[block_start:block_end + 1])
    opening = lines[block_start].strip()
    if not re.search(r":443(?:\s|>)", opening):
        continue
    if not re.search(r"(?mi)^\s*ServerName\s+edge1\.ww\.cx\s*$", block):
        continue
    if not re.search(rf"(?mi)^\s*SSLCertificateFile\s+{re.escape(fullchain)}\s*$", block):
        continue
    if not re.search(rf"(?mi)^\s*SSLCertificateKeyFile\s+{re.escape(private_key)}\s*$", block):
        continue
    matches.append((block_start, block_end))
if len(matches) != 1:
    raise SystemExit(f"expected exactly one approved TLS vhost, found {len(matches)}")

_, block_end = matches[0]
newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
lines.insert(block_end, include_line + newline)
new_text = "".join(lines)
if new_text.replace(include_line + newline, "", 1) != text:
    raise SystemExit("vhost patch changed more than the one approved include line")

metadata = path.stat()
tmp = path.with_name(path.name + ".wwcx-b2.tmp")
tmp.write_text(new_text, encoding="utf-8", newline="")
os.chmod(tmp, stat.S_IMODE(metadata.st_mode))
os.chown(tmp, metadata.st_uid, metadata.st_gid)
os.replace(tmp, path)
PY
}

restore_from_current_evidence() {
  [ -n "$EVIDENCE_DIR" ] || return 1
  [ -f "$EVIDENCE_DIR/vhost.before.conf" ] || return 1
  cp -a -- "$EVIDENCE_DIR/vhost.before.conf" "$VHOST_TARGET"
  if [ -f "$EVIDENCE_DIR/fragment.before.conf" ]; then
    cp -a -- "$EVIDENCE_DIR/fragment.before.conf" "$FRAGMENT_PATH"
  else
    rm -f -- "$FRAGMENT_PATH"
  fi
  apache2ctl configtest > "$EVIDENCE_DIR/rollback-configtest.txt" 2>&1
  systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/rollback-reload.txt" 2>&1
  systemctl is-active --quiet "$APACHE_SERVICE"
}

rollback_if_needed() {
  if [ "$MUTATION_STARTED" = true ] && [ "$ACTIVATION_ACCEPTED" != true ] && [ "$ROLLBACK_IN_PROGRESS" != true ]; then
    ROLLBACK_IN_PROGRESS=true
    echo "Phase B2 Apache activation verification failed; restoring the previous Apache configuration." >&2
    if restore_from_current_evidence; then
      printf 'automatic_rollback=pass\nrollback_state=restored\n' >> "$EVIDENCE_DIR/summary.txt"
    else
      printf 'automatic_rollback=failed\nrollback_state=uncertain\n' >> "$EVIDENCE_DIR/summary.txt"
      echo "WARNING: automatic Apache rollback failed; inspect $EVIDENCE_DIR before further action." >&2
    fi
    (
      cd "$EVIDENCE_DIR"
      find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
    ) || true
    chmod -R go-rwx "$EVIDENCE_DIR" || true
  fi
}

on_exit() {
  rc=$?
  trap - EXIT HUP INT TERM
  rollback_if_needed
  exit "$rc"
}

on_signal() {
  trap - EXIT HUP INT TERM
  rollback_if_needed
  exit 130
}

manual_rollback() {
  [ -n "$ROLLBACK_EVIDENCE" ] || fail "ROLLBACK_EVIDENCE is required for ACTION=rollback"
  [ -d "$ROLLBACK_EVIDENCE" ] || fail "rollback source evidence directory is absent"
  [ ! -L "$ROLLBACK_EVIDENCE" ] || fail "rollback source evidence must not be a symlink"
  [ "$(stat -c %u "$ROLLBACK_EVIDENCE")" -eq 0 ] || fail "rollback source evidence must be root-owned"
  [ -f "$ROLLBACK_EVIDENCE/vhost.before.conf" ] || fail "rollback source lacks the vhost backup"
  [ -f "$ROLLBACK_EVIDENCE/SHA256SUMS" ] || fail "rollback source lacks its manifest"
  (
    cd "$ROLLBACK_EVIDENCE"
    sha256sum -c SHA256SUMS >/dev/null
  ) || fail "rollback source evidence hash verification failed"
  grep -Fqx 'readiness_state=awaiting_business159_source_acceptance' "$ROLLBACK_EVIDENCE/summary.txt" || fail "rollback source is not an accepted pending B2 activation"

  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  EVIDENCE_DIR=$ROLLBACK_ROOT/$stamp
  install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
  : > "$EVIDENCE_DIR/summary.txt"
  record captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  record host "$EXPECTED_HOST"
  record principal root
  record source_activation_evidence "$ROLLBACK_EVIDENCE"
  [ -f "$ROLLBACK_EVIDENCE/vhost.after.conf" ] || fail "rollback source lacks the activated vhost snapshot"
  [ -f "$ROLLBACK_EVIDENCE/fragment.after.conf" ] || fail "rollback source lacks the activated fragment snapshot"
  [ -f "$FRAGMENT_PATH" ] || fail "live Apache fragment is absent before rollback"
  [ "$(latest_file_sha256 "$VHOST_TARGET")" = "$(latest_file_sha256 "$ROLLBACK_EVIDENCE/vhost.after.conf")" ] || fail "live vhost changed after activation; refusing to overwrite it"
  [ "$(latest_file_sha256 "$FRAGMENT_PATH")" = "$(latest_file_sha256 "$ROLLBACK_EVIDENCE/fragment.after.conf")" ] || fail "live fragment changed after activation; refusing to overwrite it"

  cp -a -- "$VHOST_TARGET" "$EVIDENCE_DIR/vhost.before-rollback.conf"
  cp -a -- "$FRAGMENT_PATH" "$EVIDENCE_DIR/fragment.before-rollback.conf"

  rollback_restore_needed=true
  rollback_restore() {
    if [ "$rollback_restore_needed" = true ]; then
      cp -a -- "$EVIDENCE_DIR/vhost.before-rollback.conf" "$VHOST_TARGET" || true
      cp -a -- "$EVIDENCE_DIR/fragment.before-rollback.conf" "$FRAGMENT_PATH" || true
      apache2ctl configtest > "$EVIDENCE_DIR/failed-rollback-restore-configtest.txt" 2>&1 || true
      systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/failed-rollback-restore-reload.txt" 2>&1 || true
    fi
  }
  trap rollback_restore EXIT HUP INT TERM

  cp -a -- "$ROLLBACK_EVIDENCE/vhost.before.conf" "$VHOST_TARGET"
  if [ -f "$ROLLBACK_EVIDENCE/fragment.before.conf" ]; then
    cp -a -- "$ROLLBACK_EVIDENCE/fragment.before.conf" "$FRAGMENT_PATH"
  else
    rm -f -- "$FRAGMENT_PATH"
  fi
  apache2ctl configtest > "$EVIDENCE_DIR/configtest.txt" 2>&1
  systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/reload.txt" 2>&1
  systemctl is-active --quiet "$APACHE_SERVICE" || fail "Apache is not active after rollback"
  if grep -R -l --binary-files=without-match 'outbound-mail/api/v1' /etc/apache2 >/dev/null 2>&1; then
    fail "preparation route remains in Apache configuration after rollback"
  fi
  direct_unsigned=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/api/v1/status || true)
  direct_send=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8104/outbound-mail/send || true)
  [ "$direct_unsigned" = 401 ] || fail "direct preparation authentication changed during rollback"
  [ "$direct_send" = 403 ] || fail "send denial changed during rollback"
  record apache_config_restored yes
  record proxy_service_reloaded yes
  record external_delivery_enabled no
  record message_sent no
  record rollback_state restored
  rollback_restore_needed=false
  trap - EXIT HUP INT TERM
  (
    cd "$EVIDENCE_DIR"
    find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
  )
  chmod -R go-rwx "$EVIDENCE_DIR"
  echo "Phase B2 Apache route rolled back successfully."
  echo "Evidence: $EVIDENCE_DIR"
}

case "$ACTION" in
  install|rollback) ;;
  *) fail "ACTION must be install or rollback" ;;
esac

verify_common_host_state

if [ "$ACTION" = rollback ]; then
  manual_rollback
  exit 0
fi

verify_proposal_evidence

trap on_exit EXIT
trap on_signal HUP INT TERM

[ ! -e "$FRAGMENT_PATH" ] && [ ! -L "$FRAGMENT_PATH" ] || fail "Apache preparation fragment already exists"
if grep -R -l --binary-files=without-match 'outbound-mail/api/v1' /etc/apache2 >/dev/null 2>&1; then
  fail "an Apache configuration already references the preparation API path"
fi
if grep -Fqx "$INCLUDE_LINE" "$VHOST_TARGET"; then
  fail "approved include line already exists in the active vhost"
fi

apache2ctl configtest >/dev/null 2>&1 || fail "Apache configuration is not valid before activation"

stamp=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR=$EVIDENCE_ROOT/$stamp
install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
: > "$EVIDENCE_DIR/summary.txt"
: > "$EVIDENCE_DIR/failures.txt"

record captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
record host "$EXPECTED_HOST"
record principal root
record repository "$REPO_ROOT"
record branch main
record head_commit "$EXPECTED_COMMIT"
record approved_activation_commit "$APPROVED_ACTIVATION_COMMIT"
record proposal_evidence "$PROPOSAL_EVIDENCE"
record proposed_hostname "$PROPOSED_HOSTNAME"
record proposed_client_cidr "$PROPOSED_CLIENT_CIDR"
record active_vhost "$ACTIVE_VHOST"
record active_vhost_resolved "$VHOST_TARGET"
record fragment_path "$FRAGMENT_PATH"

cp -a -- "$VHOST_TARGET" "$EVIDENCE_DIR/vhost.before.conf"
printf 'absent\n' > "$EVIDENCE_DIR/fragment.before.state"
render_candidate
install -o root -g root -m 0644 "$EVIDENCE_DIR/candidate-apache-fragment.conf" "$FRAGMENT_PATH"
MUTATION_STARTED=true

patch_vhost
cp -a -- "$VHOST_TARGET" "$EVIDENCE_DIR/vhost.after.conf"
cp -a -- "$FRAGMENT_PATH" "$EVIDENCE_DIR/fragment.after.conf"

diff -u "$EVIDENCE_DIR/vhost.before.conf" "$EVIDENCE_DIR/vhost.after.conf" > "$EVIDENCE_DIR/vhost.diff" || true
python3 - "$EVIDENCE_DIR/vhost.before.conf" "$EVIDENCE_DIR/vhost.after.conf" "$INCLUDE_LINE" <<'PY'
import pathlib
import sys
before = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
after = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
line = sys.argv[3]
if after.count(line) != 1:
    raise SystemExit("approved include line count is not exactly one")
if after.replace(line + "\n", "", 1) != before and after.replace(line + "\r\n", "", 1) != before:
    raise SystemExit("active vhost changed beyond the one approved include line")
PY

apache2ctl configtest > "$EVIDENCE_DIR/configtest.txt" 2>&1
systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/apache-reload.txt" 2>&1
systemctl is-active --quiet "$APACHE_SERVICE" || fail "Apache is not active after reload"
systemctl show "$APACHE_SERVICE" -p ActiveState -p SubState -p MainPID > "$EVIDENCE_DIR/apache-properties.txt"

local_status=$(curl -sS --max-time 10 --resolve edge1.ww.cx:443:127.0.0.1 -o "$EVIDENCE_DIR/local-status-response.txt" -w '%{http_code}' https://edge1.ww.cx/outbound-mail/api/v1/status || true)
local_prepare=$(curl -sS --max-time 10 --resolve edge1.ww.cx:443:127.0.0.1 -H 'Content-Type: application/json' -d '{}' -o "$EVIDENCE_DIR/local-prepare-response.txt" -w '%{http_code}' https://edge1.ww.cx/outbound-mail/api/v1/prepare || true)
local_send=$(curl -sS --max-time 10 --resolve edge1.ww.cx:443:127.0.0.1 -H 'Content-Type: application/json' -d '{}' -o "$EVIDENCE_DIR/local-send-response.txt" -w '%{http_code}' https://edge1.ww.cx/outbound-mail/send || true)
local_health=$(curl -sS --max-time 10 --resolve edge1.ww.cx:443:127.0.0.1 -o "$EVIDENCE_DIR/local-health-response.txt" -w '%{http_code}' https://edge1.ww.cx/outbound-mail/healthz || true)

[ "$local_status" = 403 ] || fail "unapproved local source was not denied on the status route"
[ "$local_prepare" = 403 ] || fail "unapproved local source was not denied on the prepare route"
[ "$local_send" = 404 ] || fail "HTTPS send route is unexpectedly exposed"
[ "$local_health" = 404 ] || fail "HTTPS health route is unexpectedly exposed"

direct_unsigned=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/api/v1/status || true)
direct_send=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8104/outbound-mail/send || true)
[ "$direct_unsigned" = 401 ] || fail "direct preparation authentication changed after Apache activation"
[ "$direct_send" = 403 ] || fail "direct send denial changed after Apache activation"

record local_unapproved_status_http "$local_status"
record local_unapproved_prepare_http "$local_prepare"
record https_send_http "$local_send"
record https_health_http "$local_health"
record direct_unsigned_status_http "$direct_unsigned"
record direct_send_http "$direct_send"
record certificate_private_key_exposed no
record certificate_key_pair_validated_by_apache yes
record hmac_secret_read no
record proxy_config_installed yes
record proxy_service_reloaded yes
record certificate_generated no
record dns_modified no
record firewall_modified no
record public_listener_added no
record website_bridge_enabled no
record provider_or_sender_enabled no
record external_delivery_enabled no
record message_sent no
record approved_source_external_canary not_yet_run
record readiness_state awaiting_business159_source_acceptance
record failures 0

(
  cd "$EVIDENCE_DIR"
  find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
)
chmod -R go-rwx "$EVIDENCE_DIR"

ACTIVATION_ACCEPTED=true
trap - EXIT HUP INT TERM

echo "Phase B2 Apache route activated with exact-source restriction."
echo "Business159 external source acceptance is still required."
echo "No provider, sender, external delivery, or message state was enabled."
echo "Evidence: $EVIDENCE_DIR"
