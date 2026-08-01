#!/bin/sh
set -eu

umask 077

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
SERVICE_NAME=${SERVICE_NAME:-wwcx-outbound-mail-gateway.service}
EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
B1_LIVE_ACCEPTANCE_COMMIT=${B1_LIVE_ACCEPTANCE_COMMIT:-53bb0ea15cdedb136add858841813273252cc8fc}
B2_BASELINE_COMMIT=${B2_BASELINE_COMMIT:-f1f65571902c7f377c6a7ca9c52f634973a7635a}
PROPOSED_HOSTNAME=${PROPOSED_HOSTNAME:-}
PROPOSED_CLIENT_CIDR=${PROPOSED_CLIENT_CIDR:-}
CERTIFICATE_FULLCHAIN_PATH=${CERTIFICATE_FULLCHAIN_PATH:-}
CERTIFICATE_PRIVATE_KEY_PATH=${CERTIFICATE_PRIVATE_KEY_PATH:-}
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-readiness
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root so service, listener, firewall, certificate, and restricted runtime-file metadata can be inspected." >&2
  exit 77
fi

if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "Repository not found at $REPO_ROOT" >&2
  exit 1
fi

host_fqdn=$(hostname -f 2>/dev/null || hostname)
if [ "$host_fqdn" != "$EXPECTED_HOST" ]; then
  echo "Host mismatch: expected $EXPECTED_HOST, observed $host_fqdn" >&2
  exit 1
fi

output_dir="$EVIDENCE_ROOT/$TIMESTAMP"
install -d -m 0700 "$output_dir"
summary="$output_dir/summary.txt"
failures="$output_dir/failures.txt"
decisions="$output_dir/pending-decisions.txt"
: > "$summary"
: > "$failures"
: > "$decisions"

record() {
  printf '%s=%s\n' "$1" "$2" >> "$summary"
}

fail() {
  printf '%s\n' "$1" >> "$failures"
}

pending() {
  printf '%s\n' "$1" >> "$decisions"
}

branch=$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)
if head_commit=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null); then
  :
else
  head_commit=unknown
  fail "repository HEAD could not be resolved"
fi

record captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
record host "$host_fqdn"
record principal "$(id -un)"
record repository "$REPO_ROOT"
record branch "${branch:-detached}"
record head_commit "$head_commit"
record b1_live_acceptance_commit "$B1_LIVE_ACCEPTANCE_COMMIT"
record b2_baseline_commit "$B2_BASELINE_COMMIT"
record evidence_root "$EVIDENCE_ROOT"
record proposed_hostname "${PROPOSED_HOSTNAME:-not_supplied}"
record proposed_client_cidr "${PROPOSED_CLIENT_CIDR:-not_supplied}"
record certificate_fullchain_path "${CERTIFICATE_FULLCHAIN_PATH:-not_supplied}"
record certificate_private_key_path "${CERTIFICATE_PRIVATE_KEY_PATH:-not_supplied}"

if [ "$branch" != main ]; then
  fail "repository branch is not main"
fi
if [ -n "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=all 2>/dev/null || true)" ]; then
  fail "repository contains tracked or untracked changes"
fi
if ! git -C "$REPO_ROOT" merge-base --is-ancestor "$B1_LIVE_ACCEPTANCE_COMMIT" HEAD; then
  fail "accepted B1 live-state commit is not an ancestor of HEAD"
fi
if ! git -C "$REPO_ROOT" merge-base --is-ancestor "$B2_BASELINE_COMMIT" HEAD; then
  fail "approved B2 template baseline is not an ancestor of HEAD"
fi

protected_paths='deploy/messaging/outbound-mail-preparation-api-nginx.conf.example
docs/messaging-operations/outbound-mail-phase-b-preparation-20260801.md
server/outbound_mail_gateway.py
server/outbound_mail_gateway_server.py
server/outbound_mail_preparation_auth.py
tools/outbound_mail_preparation_canary.py
config/messaging/outbound-mail-gateway.json
config/messaging/outbound-mail-policy.json
config/messaging/mail-identities.json'
printf '%s\n' "$protected_paths" > "$output_dir/protected-paths.txt"
if ! git -C "$REPO_ROOT" diff --quiet "$B2_BASELINE_COMMIT"..HEAD -- $protected_paths; then
  fail "protected B2 files changed after the approved baseline"
  git -C "$REPO_ROOT" diff --name-only "$B2_BASELINE_COMMIT"..HEAD -- $protected_paths \
    > "$output_dir/protected-path-changes.txt" || true
else
  : > "$output_dir/protected-path-changes.txt"
fi

git -C "$REPO_ROOT" status --short --branch --untracked-files=all > "$output_dir/git-status.txt" 2>&1 || \
  fail "git status capture failed"
git -C "$REPO_ROOT" log -1 --format='commit=%H%nauthor_date=%aI%ncommitter_date=%cI%nsubject=%s' \
  > "$output_dir/git-head.txt" 2>&1 || fail "git HEAD metadata capture failed"

TEMPLATE="$REPO_ROOT/deploy/messaging/outbound-mail-preparation-api-nginx.conf.example"
if ! python3 - "$TEMPLATE" "$output_dir/template-validation.json" \
  2> "$output_dir/template-validation-error.txt" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
text = path.read_text(encoding="utf-8")
required = (
    "PREPARATION_API_HOSTNAME",
    "CERTIFICATE_FULLCHAIN_PATH",
    "CERTIFICATE_PRIVATE_KEY_PATH",
    "PREPARATION_CLIENT_CIDR",
    "location = /outbound-mail/api/v1/status",
    "limit_except GET",
    "location = /outbound-mail/api/v1/prepare",
    "limit_except POST",
    "proxy_pass http://127.0.0.1:8104",
    "proxy_redirect off",
    "client_max_body_size 320k",
    "ssl_protocols TLSv1.2 TLSv1.3",
    "location /",
    "return 404",
)
missing = [value for value in required if value not in text]
state = {
    "missing_required_fragments": missing,
    "status_location_count": text.count("location = /outbound-mail/api/v1/status"),
    "prepare_location_count": text.count("location = /outbound-mail/api/v1/prepare"),
    "send_route_present": "/outbound-mail/send" in text,
    "wildcard_proxy_location_present": "location /outbound-mail/api/" in text,
}
out.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if missing:
    raise SystemExit("staged B2 template is missing required safety fragments")
if state["status_location_count"] != 1 or state["prepare_location_count"] != 1:
    raise SystemExit("staged B2 template does not expose exactly one status and one prepare location")
if state["send_route_present"] or state["wildcard_proxy_location_present"]:
    raise SystemExit("staged B2 template contains an unauthorized route")
PY
then
  fail "staged B2 template validation failed"
fi

if ! systemctl is-active --quiet "$SERVICE_NAME"; then
  fail "$SERVICE_NAME is not active"
fi
if ! systemctl is-enabled --quiet "$SERVICE_NAME"; then
  fail "$SERVICE_NAME is not enabled"
fi
systemctl status "$SERVICE_NAME" --no-pager --lines=0 -l \
  > "$output_dir/service-status.txt" 2>&1 || true
systemctl show "$SERVICE_NAME" \
  -p ActiveState -p SubState -p UnitFileState -p FragmentPath -p DropInPaths \
  -p User -p Group -p ExecStart -p MainPID -p EnvironmentFiles \
  > "$output_dir/service-properties.txt" 2>&1 || fail "service property capture failed"
if ! systemctl show "$SERVICE_NAME" -p User --value 2>/dev/null | grep -qx 'wwcx-mail-gateway'; then
  fail "service principal is not wwcx-mail-gateway"
fi

ss -lntp > "$output_dir/listeners.txt" 2>&1 || fail "listener inventory failed"
port_addresses="$output_dir/port-8104-addresses.txt"
ss -lnt 2>/dev/null | awk 'NR > 1 {print $4}' | grep -E ':8104$' > "$port_addresses" || true
if ! grep -qx '127.0.0.1:8104' "$port_addresses"; then
  fail "loopback listener 127.0.0.1:8104 was not observed"
fi
if grep -Ev '^127\.0\.0\.1:8104$' "$port_addresses" | grep -q .; then
  fail "port 8104 has a non-approved listener address"
fi
ss -lntp 2>/dev/null | awk 'NR == 1 || $4 ~ /:443$/' > "$output_dir/port-443-listeners.txt" || true

curl -fsS --max-time 5 http://127.0.0.1:8104/outbound-mail/healthz \
  > "$output_dir/health.json" || fail "health endpoint did not return HTTP 200"
curl -fsS --max-time 5 http://127.0.0.1:8104/outbound-mail/status \
  > "$output_dir/status.json" || fail "status endpoint did not return HTTP 200"
api_code=$(curl -sS --max-time 5 -o "$output_dir/unsigned-api-status.json" -w '%{http_code}' \
  http://127.0.0.1:8104/outbound-mail/api/v1/status || true)
record unsigned_api_status_http "$api_code"
if [ "$api_code" != 401 ]; then
  fail "unsigned preparation API status did not return HTTP 401 in accepted B1 state"
fi
send_code=$(curl -sS --max-time 5 -o "$output_dir/send-probe.json" -w '%{http_code}' \
  -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8104/outbound-mail/send || true)
record send_probe_http "$send_code"
if [ "$send_code" != 403 ]; then
  fail "send probe did not return HTTP 403"
fi

if ! python3 - "$output_dir/status.json" 2> "$output_dir/status-validation-error.txt" <<'PY'
import json
import pathlib
import sys

status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert status["state"] == "disabled"
assert status["preparation_api"]["enabled"] is True
assert status["preparation_api"]["runtime_secret_configured"] is True
assert status["external_delivery_enabled"] is False
assert status["policy_enabled"] is False
assert status["sender_selection"]["live_sender_count"] == 0
assert not any(item["ready"] for item in status["providers"])
PY
then
  fail "runtime status does not match accepted loopback-only B1 state"
fi

runtime_metadata="$output_dir/runtime-file-metadata.tsv"
printf 'path\tpresent\ttype\tuid\tmode\tbytes\n' > "$runtime_metadata"
check_runtime_file() {
  path=$1
  expected_mode=$2
  if [ ! -e "$path" ] || [ -L "$path" ]; then
    printf '%s\tno\t-\t-\t-\t-\n' "$path" >> "$runtime_metadata"
    fail "required B1 runtime file is absent or symlinked: $path"
    return
  fi
  type=$(stat -c %F "$path")
  uid=$(stat -c %u "$path")
  mode=$(stat -c %a "$path")
  bytes=$(stat -c %s "$path")
  printf '%s\tyes\t%s\t%s\t%s\t%s\n' "$path" "$type" "$uid" "$mode" "$bytes" >> "$runtime_metadata"
  [ "$type" = "regular file" ] || fail "B1 runtime path is not a regular file: $path"
  [ "$uid" = 0 ] || fail "B1 runtime path is not root-owned: $path"
  [ "$mode" = "$expected_mode" ] || fail "B1 runtime path has unexpected mode $mode: $path"
  [ "$bytes" -gt 0 ] || fail "B1 runtime path is empty: $path"
}
check_runtime_file /etc/wwcx/outbound-mail-gateway.json 644
check_runtime_file /etc/wwcx/outbound-mail-gateway.env 600
check_runtime_file /etc/systemd/system/wwcx-outbound-mail-gateway.service.d/20-preparation-api.conf 644

proxy_matches="$output_dir/proxy-path-matches.txt"
: > "$proxy_matches"
for root in /etc/nginx /etc/apache2 /etc/httpd /etc/caddy; do
  if [ -d "$root" ]; then
    grep -R -l --binary-files=without-match 'outbound-mail/api/v1' "$root" 2>/dev/null \
      >> "$proxy_matches" || true
  fi
done
sort -u "$proxy_matches" -o "$proxy_matches"
if [ -s "$proxy_matches" ]; then
  fail "an existing web-server configuration already references the preparation API path"
fi

: > "$output_dir/web-server-inventory.txt"
for command_name in nginx apache2 httpd caddy; do
  if command -v "$command_name" >/dev/null 2>&1; then
    printf '%s=%s\n' "$command_name" "$(command -v "$command_name")" >> "$output_dir/web-server-inventory.txt"
    "$command_name" -v >> "$output_dir/web-server-inventory.txt" 2>&1 || true
  else
    printf '%s=absent\n' "$command_name" >> "$output_dir/web-server-inventory.txt"
  fi
done
for unit in nginx.service apache2.service httpd.service caddy.service; do
  printf '%s active=%s enabled=%s\n' "$unit" \
    "$(systemctl is-active "$unit" 2>/dev/null || true)" \
    "$(systemctl is-enabled "$unit" 2>/dev/null || true)" \
    >> "$output_dir/web-server-services.txt"
done

: > "$output_dir/firewall-inventory.txt"
if command -v nft >/dev/null 2>&1; then
  nft list ruleset > "$output_dir/nftables-ruleset.txt" 2>&1 || true
  echo 'nft=present' >> "$output_dir/firewall-inventory.txt"
else
  echo 'nft=absent' >> "$output_dir/firewall-inventory.txt"
fi
if command -v iptables-save >/dev/null 2>&1; then
  iptables-save > "$output_dir/iptables-rules.txt" 2>&1 || true
  echo 'iptables-save=present' >> "$output_dir/firewall-inventory.txt"
else
  echo 'iptables-save=absent' >> "$output_dir/firewall-inventory.txt"
fi
if command -v ip6tables-save >/dev/null 2>&1; then
  ip6tables-save > "$output_dir/ip6tables-rules.txt" 2>&1 || true
  echo 'ip6tables-save=present' >> "$output_dir/firewall-inventory.txt"
else
  echo 'ip6tables-save=absent' >> "$output_dir/firewall-inventory.txt"
fi
if command -v ufw >/dev/null 2>&1; then
  ufw status verbose > "$output_dir/ufw-status.txt" 2>&1 || true
  echo 'ufw=present' >> "$output_dir/firewall-inventory.txt"
else
  echo 'ufw=absent' >> "$output_dir/firewall-inventory.txt"
fi

supplied_count=0
[ -n "$PROPOSED_HOSTNAME" ] && supplied_count=$((supplied_count + 1))
[ -n "$PROPOSED_CLIENT_CIDR" ] && supplied_count=$((supplied_count + 1))
[ -n "$CERTIFICATE_FULLCHAIN_PATH" ] && supplied_count=$((supplied_count + 1))
[ -n "$CERTIFICATE_PRIVATE_KEY_PATH" ] && supplied_count=$((supplied_count + 1))

if [ "$supplied_count" -eq 0 ]; then
  pending "exact B2 hostname has not been supplied"
  pending "exact single-source client CIDR has not been supplied"
  pending "certificate full-chain path has not been supplied"
  pending "certificate private-key path has not been supplied"
elif [ "$supplied_count" -ne 4 ]; then
  fail "B2 proposal inputs are partial; supply all four or none"
else
  if ! python3 - "$PROPOSED_HOSTNAME" "$PROPOSED_CLIENT_CIDR" \
    > "$output_dir/proposal-validation.txt" 2> "$output_dir/proposal-validation-error.txt" <<'PY'
import ipaddress
import re
import sys

hostname = sys.argv[1]
cidr_text = sys.argv[2]
if hostname != hostname.lower() or hostname.endswith(".") or "*" in hostname:
    raise SystemExit("hostname must be a lowercase non-wildcard FQDN without a trailing dot")
if len(hostname) > 253 or "." not in hostname:
    raise SystemExit("hostname must be a valid FQDN")
for label in hostname.split("."):
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label):
        raise SystemExit("hostname contains an invalid DNS label")
try:
    ipaddress.ip_address(hostname)
except ValueError:
    pass
else:
    raise SystemExit("hostname must not be an IP literal")
network = ipaddress.ip_network(cidr_text, strict=True)
if network.prefixlen != network.max_prefixlen:
    raise SystemExit("client source must be one exact IPv4 /32 or IPv6 /128 address")
print(f"hostname={hostname}")
print(f"client_network={network}")
PY
  then
    fail "B2 hostname or client CIDR validation failed"
  fi

  getent ahosts "$PROPOSED_HOSTNAME" > "$output_dir/hostname-getent.txt" 2>&1 || true
  if command -v dig >/dev/null 2>&1; then
    dig +short A "$PROPOSED_HOSTNAME" > "$output_dir/hostname-a.txt" 2>&1 || true
    dig +short AAAA "$PROPOSED_HOSTNAME" > "$output_dir/hostname-aaaa.txt" 2>&1 || true
  else
    : > "$output_dir/hostname-a.txt"
    : > "$output_dir/hostname-aaaa.txt"
  fi
  if [ ! -s "$output_dir/hostname-getent.txt" ] && \
     [ ! -s "$output_dir/hostname-a.txt" ] && \
     [ ! -s "$output_dir/hostname-aaaa.txt" ]; then
    pending "proposed hostname does not currently resolve; DNS change remains separately gated"
  fi

  if [ ! -e "$CERTIFICATE_FULLCHAIN_PATH" ] || [ -L "$CERTIFICATE_FULLCHAIN_PATH" ]; then
    fail "certificate full-chain path is absent or symlinked"
  else
    cert_type=$(stat -c %F "$CERTIFICATE_FULLCHAIN_PATH")
    cert_uid=$(stat -c %u "$CERTIFICATE_FULLCHAIN_PATH")
    cert_mode=$(stat -c %a "$CERTIFICATE_FULLCHAIN_PATH")
    cert_bytes=$(stat -c %s "$CERTIFICATE_FULLCHAIN_PATH")
    printf 'path=%s\ntype=%s\nuid=%s\nmode=%s\nbytes=%s\n' \
      "$CERTIFICATE_FULLCHAIN_PATH" "$cert_type" "$cert_uid" "$cert_mode" "$cert_bytes" \
      > "$output_dir/certificate-fullchain-metadata.txt"
    [ "$cert_type" = "regular file" ] || fail "certificate full-chain path is not a regular file"
    [ "$cert_uid" = 0 ] || fail "certificate full-chain path is not root-owned"
    [ "$cert_bytes" -gt 0 ] || fail "certificate full-chain path is empty"
    if command -v openssl >/dev/null 2>&1; then
      openssl x509 -in "$CERTIFICATE_FULLCHAIN_PATH" -noout \
        -subject -issuer -serial -dates -fingerprint -sha256 -ext subjectAltName \
        > "$output_dir/certificate-public-details.txt" 2>&1 || fail "certificate public metadata inspection failed"
      openssl x509 -in "$CERTIFICATE_FULLCHAIN_PATH" -noout -checkhost "$PROPOSED_HOSTNAME" \
        > "$output_dir/certificate-hostname-check.txt" 2>&1 || fail "certificate does not cover the proposed hostname"
      openssl x509 -in "$CERTIFICATE_FULLCHAIN_PATH" -noout -checkend 604800 \
        > "$output_dir/certificate-expiry-check.txt" 2>&1 || fail "certificate expires within seven days"
    else
      fail "openssl is unavailable for public certificate inspection"
    fi
  fi

  if [ ! -e "$CERTIFICATE_PRIVATE_KEY_PATH" ] || [ -L "$CERTIFICATE_PRIVATE_KEY_PATH" ]; then
    fail "certificate private-key path is absent or symlinked"
  else
    key_type=$(stat -c %F "$CERTIFICATE_PRIVATE_KEY_PATH")
    key_uid=$(stat -c %u "$CERTIFICATE_PRIVATE_KEY_PATH")
    key_mode=$(stat -c %a "$CERTIFICATE_PRIVATE_KEY_PATH")
    key_bytes=$(stat -c %s "$CERTIFICATE_PRIVATE_KEY_PATH")
    printf 'path=%s\ntype=%s\nuid=%s\nmode=%s\nbytes=%s\ncontents_read=no\n' \
      "$CERTIFICATE_PRIVATE_KEY_PATH" "$key_type" "$key_uid" "$key_mode" "$key_bytes" \
      > "$output_dir/certificate-private-key-metadata.txt"
    [ "$key_type" = "regular file" ] || fail "certificate private-key path is not a regular file"
    [ "$key_uid" = 0 ] || fail "certificate private-key path is not root-owned"
    case "$key_mode" in
      400|600) : ;;
      *) fail "certificate private-key path mode must be 0400 or 0600" ;;
    esac
    [ "$key_bytes" -gt 0 ] || fail "certificate private-key path is empty"
  fi

  if ! python3 - "$TEMPLATE" "$output_dir/candidate-nginx.conf" \
    "$PROPOSED_HOSTNAME" "$PROPOSED_CLIENT_CIDR" \
    "$CERTIFICATE_FULLCHAIN_PATH" "$CERTIFICATE_PRIVATE_KEY_PATH" \
    2> "$output_dir/candidate-render-error.txt" <<'PY'
import pathlib
import sys

template = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
out = pathlib.Path(sys.argv[2])
values = {
    "PREPARATION_API_HOSTNAME": sys.argv[3],
    "PREPARATION_CLIENT_CIDR": sys.argv[4],
    "CERTIFICATE_FULLCHAIN_PATH": sys.argv[5],
    "CERTIFICATE_PRIVATE_KEY_PATH": sys.argv[6],
}
for key, value in values.items():
    template = template.replace(key, value)
if any(key in template for key in values):
    raise SystemExit("candidate contains an unreplaced placeholder")
if "/outbound-mail/send" in template:
    raise SystemExit("candidate contains an unauthorized send route")
out.write_text(template, encoding="utf-8")
PY
  then
    fail "candidate B2 configuration rendering failed"
  fi
fi

if [ -s "$failures" ]; then
  readiness_state=not_ready
elif [ "$supplied_count" -eq 0 ]; then
  readiness_state=awaiting_explicit_b2_parameters
elif [ -s "$decisions" ]; then
  readiness_state=awaiting_separately_authorized_dns_or_parameter_resolution
else
  readiness_state=ready_for_explicit_b2_authorization
fi
record readiness_state "$readiness_state"
record hmac_secret_read no
record certificate_private_key_read no
record candidate_config_written_to_evidence_only yes
record proxy_config_installed no
record proxy_service_reloaded no
record certificate_generated no
record dns_modified no
record firewall_modified no
record public_listener_added no
record website_bridge_enabled no
record provider_or_sender_enabled no
record message_sent no

(
  cd "$output_dir"
  find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
)
chmod -R go-rwx "$output_dir"

cat "$summary"
if [ -s "$decisions" ]; then
  echo "Pending decisions:" >&2
  cat "$decisions" >&2
fi
if [ -s "$failures" ]; then
  echo "B2 readiness audit failed:" >&2
  cat "$failures" >&2
  echo "Evidence: $output_dir" >&2
  exit 1
fi

echo "Phase B2 read-only readiness audit completed."
echo "No secret or private-key contents were read, and no runtime or network state was changed."
echo "Evidence: $output_dir"
