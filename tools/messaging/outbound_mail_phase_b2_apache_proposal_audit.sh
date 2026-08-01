#!/bin/sh
set -eu
umask 077

REPO=${REPO:-/opt/edge1-management-interface}
EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
DISCOVERY_FIX_COMMIT=${DISCOVERY_FIX_COMMIT:-672461ce0f996871be7613a5d6c16bf4950e986d}
SERVICE=${SERVICE:-wwcx-outbound-mail-gateway.service}
PORT=${PORT:-8104}
PROPOSED_HOSTNAME=${PROPOSED_HOSTNAME:-edge1.ww.cx}
PROPOSED_CLIENT_CIDR=${PROPOSED_CLIENT_CIDR:-162.0.217.71/32}
CERTIFICATE_FULLCHAIN_PATH=${CERTIFICATE_FULLCHAIN_PATH:-/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem}
CERTIFICATE_PRIVATE_KEY_PATH=${CERTIFICATE_PRIVATE_KEY_PATH:-/etc/letsencrypt/live/edge1.ww.cx/privkey.pem}
ACTIVE_VHOST=${ACTIVE_VHOST:-/etc/apache2/sites-enabled/edge1.ww.cx.conf}
TEMPLATE=${TEMPLATE:-$REPO/deploy/messaging/outbound-mail-preparation-api-apache.conf.example}
EVIDENCE_ROOT=${EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal}

failures=0

fail() {
    printf '%s\n' "$*" >> "$output_dir/failures.txt"
    failures=$((failures + 1))
}

record() {
    printf '%s=%s\n' "$1" "$2" >> "$output_dir/summary.txt"
}

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root for restricted certificate pathname metadata and service inspection." >&2
    exit 77
fi

host_fqdn=$(hostname -f 2>/dev/null || hostname)
if [ "$host_fqdn" != "$EXPECTED_HOST" ]; then
    echo "Host mismatch: expected $EXPECTED_HOST but found $host_fqdn" >&2
    exit 1
fi

cd "$REPO"
branch=$(git branch --show-current)
head_commit=$(git rev-parse HEAD)
status=$(git status --porcelain --untracked-files=all)
if [ "$branch" != main ]; then
    echo "Repository branch must be main." >&2
    exit 1
fi
if [ -n "$status" ]; then
    echo "Repository working tree must be clean." >&2
    git status --short >&2
    exit 1
fi
if ! git merge-base --is-ancestor "$DISCOVERY_FIX_COMMIT" "$head_commit"; then
    echo "Required discovery remediation is not an ancestor of HEAD." >&2
    exit 1
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
output_dir="$EVIDENCE_ROOT/$stamp"
install -d -m 0700 "$output_dir"
: > "$output_dir/failures.txt"
: > "$output_dir/summary.txt"

record captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
record host "$host_fqdn"
record principal "$(id -un)"
record repository "$REPO"
record branch "$branch"
record head_commit "$head_commit"
record proposed_hostname "$PROPOSED_HOSTNAME"
record proposed_client_cidr "$PROPOSED_CLIENT_CIDR"
record certificate_fullchain_path "$CERTIFICATE_FULLCHAIN_PATH"
record certificate_private_key_path "$CERTIFICATE_PRIVATE_KEY_PATH"
record active_vhost "$ACTIVE_VHOST"

if ! python3 - "$PROPOSED_HOSTNAME" "$PROPOSED_CLIENT_CIDR" \
    > "$output_dir/parameter-validation.txt" \
    2> "$output_dir/parameter-validation-error.txt" <<'PY'
import ipaddress
import re
import sys

hostname = sys.argv[1]
cidr = sys.argv[2]
if hostname != "edge1.ww.cx":
    raise SystemExit("hostname must be exactly edge1.ww.cx")
if not re.fullmatch(r"[a-z0-9.-]+", hostname):
    raise SystemExit("hostname contains invalid characters")
network = ipaddress.ip_network(cidr, strict=True)
if network.prefixlen != network.max_prefixlen:
    raise SystemExit("client source must be one exact IPv4 /32 or IPv6 /128")
print(f"hostname={hostname}")
print(f"client_network={network}")
PY
then
    fail "proposal hostname or client CIDR validation failed"
fi

systemctl is-active "$SERVICE" > "$output_dir/service-active.txt" 2>&1 || fail "$SERVICE is not active"
systemctl is-enabled "$SERVICE" > "$output_dir/service-enabled.txt" 2>&1 || fail "$SERVICE is not enabled"
systemctl show "$SERVICE" -p User -p ActiveState -p SubState -p FragmentPath -p DropInPaths -p EnvironmentFiles \
    > "$output_dir/service-properties.txt" 2>&1 || fail "could not inspect gateway service properties"

ss -lntp > "$output_dir/listeners.txt" 2>&1 || fail "could not capture listener inventory"
if ! awk -v port=":$PORT" '$4 ~ /127\.0\.0\.1:/ && index($4, port) {found=1} END {exit !found}' "$output_dir/listeners.txt"; then
    fail "gateway listener was not found on 127.0.0.1:$PORT"
fi
if awk -v port=":$PORT" '$4 !~ /127\.0\.0\.1:/ && index($4, port) {found=1} END {exit !found}' "$output_dir/listeners.txt"; then
    fail "gateway port $PORT is exposed beyond IPv4 loopback"
fi
if ! awk '$4 ~ /:443$/ {found=1} END {exit !found}' "$output_dir/listeners.txt"; then
    fail "no active port 443 listener was found"
fi

health_http=$(curl -sS -o "$output_dir/health.json" -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:$PORT/outbound-mail/healthz" || printf 000)
status_http=$(curl -sS -o "$output_dir/status.json" -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:$PORT/outbound-mail/status" || printf 000)
unsigned_http=$(curl -sS -o "$output_dir/unsigned-api-status.json" -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:$PORT/outbound-mail/api/v1/status" || printf 000)
send_http=$(curl -sS -o "$output_dir/send-probe.json" -w '%{http_code}' --max-time 5 \
    -H 'Content-Type: application/json' -d '{}' \
    "http://127.0.0.1:$PORT/outbound-mail/send" || printf 000)
record health_http "$health_http"
record status_http "$status_http"
record unsigned_api_status_http "$unsigned_http"
record send_probe_http "$send_http"
[ "$health_http" = 200 ] || fail "gateway health did not return HTTP 200"
[ "$status_http" = 200 ] || fail "gateway status did not return HTTP 200"
[ "$unsigned_http" = 401 ] || fail "unsigned preparation status did not return HTTP 401"
[ "$send_http" = 403 ] || fail "send probe did not return HTTP 403"

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
    fail "runtime status does not match accepted B1 no-send state"
fi

systemctl is-active apache2.service > "$output_dir/apache-active.txt" 2>&1 || fail "apache2.service is not active"
systemctl is-enabled apache2.service > "$output_dir/apache-enabled.txt" 2>&1 || fail "apache2.service is not enabled"
for module in proxy.load proxy_http.load authz_core.load authz_host.load ssl.load; do
    if [ ! -L "/etc/apache2/mods-enabled/$module" ]; then
        fail "required Apache module link is absent: $module"
    fi
done
find /etc/apache2/mods-enabled -maxdepth 1 -type l -printf '%f -> %l\n' | sort \
    > "$output_dir/apache-modules-enabled.txt" 2>&1 || fail "could not inventory enabled Apache modules"

if [ ! -L "$ACTIVE_VHOST" ]; then
    fail "active edge1 Apache vhost is not an enabled-site symlink"
    active_vhost_resolved=""
else
    active_vhost_resolved=$(readlink -f "$ACTIVE_VHOST" || true)
fi
record active_vhost_resolved "${active_vhost_resolved:-unresolved}"
case "$active_vhost_resolved" in
    /etc/apache2/sites-available/*) : ;;
    *) fail "active edge1 Apache vhost does not resolve under sites-available" ;;
esac
if [ -n "$active_vhost_resolved" ] && [ -f "$active_vhost_resolved" ]; then
    stat -Lc 'path=%n type=%F owner=%U:%G mode=%a bytes=%s' "$ACTIVE_VHOST" \
        > "$output_dir/active-vhost-metadata.txt" 2>&1 || fail "could not inspect active vhost metadata"
else
    fail "active edge1 Apache vhost target is absent"
fi

servername_count=$(awk '$1 == "ServerName" && $2 == "edge1.ww.cx" {count++} END {print count+0}' "$ACTIVE_VHOST" 2>/dev/null || printf 0)
fullchain_ref_count=$(awk -v path="$CERTIFICATE_FULLCHAIN_PATH" '$1 == "SSLCertificateFile" && $2 == path {count++} END {print count+0}' "$ACTIVE_VHOST" 2>/dev/null || printf 0)
private_key_ref_count=$(awk -v path="$CERTIFICATE_PRIVATE_KEY_PATH" '$1 == "SSLCertificateKeyFile" && $2 == path {count++} END {print count+0}' "$ACTIVE_VHOST" 2>/dev/null || printf 0)
record edge1_servername_count "$servername_count"
record fullchain_reference_count "$fullchain_ref_count"
record private_key_reference_count "$private_key_ref_count"
[ "$servername_count" -ge 1 ] || fail "enabled vhost does not name edge1.ww.cx"
[ "$fullchain_ref_count" -eq 1 ] || fail "enabled vhost does not contain exactly one approved full-chain reference"
[ "$private_key_ref_count" -eq 1 ] || fail "enabled vhost does not contain exactly one approved private-key reference"

grep -RIn --include='*.conf' 'outbound-mail/api/v1' /etc/apache2 \
    > "$output_dir/existing-preparation-route-references.txt" 2>/dev/null || true
if [ -s "$output_dir/existing-preparation-route-references.txt" ]; then
    fail "an Apache configuration already references the preparation API path"
fi

if [ "$CERTIFICATE_FULLCHAIN_PATH" != /etc/letsencrypt/live/edge1.ww.cx/fullchain.pem ]; then
    fail "full-chain path is not the approved live path"
fi
if [ "$CERTIFICATE_PRIVATE_KEY_PATH" != /etc/letsencrypt/live/edge1.ww.cx/privkey.pem ]; then
    fail "private-key path is not the approved live path"
fi
if [ ! -L "$CERTIFICATE_FULLCHAIN_PATH" ]; then
    fail "approved full-chain live path is not a symlink"
fi
if [ ! -L "$CERTIFICATE_PRIVATE_KEY_PATH" ]; then
    fail "approved private-key live path is not a symlink"
fi

fullchain_resolved=$(readlink -f "$CERTIFICATE_FULLCHAIN_PATH" || true)
private_key_resolved=$(readlink -f "$CERTIFICATE_PRIVATE_KEY_PATH" || true)
record certificate_fullchain_resolved "${fullchain_resolved:-unresolved}"
record certificate_private_key_resolved "${private_key_resolved:-unresolved}"
case "$fullchain_resolved" in
    /etc/letsencrypt/archive/edge1.ww.cx/fullchain*.pem) : ;;
    *) fail "full-chain symlink target is outside the approved archive directory" ;;
esac
case "$private_key_resolved" in
    /etc/letsencrypt/archive/edge1.ww.cx/privkey*.pem) : ;;
    *) fail "private-key symlink target is outside the approved archive directory" ;;
esac

if [ -n "$fullchain_resolved" ] && [ -f "$fullchain_resolved" ]; then
    cert_type=$(stat -Lc %F "$CERTIFICATE_FULLCHAIN_PATH")
    cert_uid=$(stat -Lc %u "$CERTIFICATE_FULLCHAIN_PATH")
    cert_mode=$(stat -Lc %a "$CERTIFICATE_FULLCHAIN_PATH")
    cert_bytes=$(stat -Lc %s "$CERTIFICATE_FULLCHAIN_PATH")
    printf 'configured_path=%s\nresolved_path=%s\ntype=%s\nuid=%s\nmode=%s\nbytes=%s\n' \
        "$CERTIFICATE_FULLCHAIN_PATH" "$fullchain_resolved" "$cert_type" "$cert_uid" "$cert_mode" "$cert_bytes" \
        > "$output_dir/certificate-fullchain-path-metadata.txt"
    [ "$cert_type" = "regular file" ] || fail "resolved full-chain target is not a regular file"
    [ "$cert_uid" = 0 ] || fail "resolved full-chain target is not root-owned"
    [ "$cert_bytes" -gt 0 ] || fail "resolved full-chain target is empty"
    openssl x509 -in "$CERTIFICATE_FULLCHAIN_PATH" -noout \
        -subject -issuer -serial -dates -fingerprint -sha256 -ext subjectAltName \
        > "$output_dir/certificate-public-details.txt" 2>&1 || fail "public certificate metadata inspection failed"
    openssl x509 -in "$CERTIFICATE_FULLCHAIN_PATH" -noout -checkhost "$PROPOSED_HOSTNAME" \
        > "$output_dir/certificate-hostname-check.txt" 2>&1 || fail "certificate does not cover the proposed hostname"
    openssl x509 -in "$CERTIFICATE_FULLCHAIN_PATH" -noout -checkend 604800 \
        > "$output_dir/certificate-expiry-check.txt" 2>&1 || fail "certificate expires within seven days"
else
    fail "resolved full-chain target is absent"
fi

if [ -n "$private_key_resolved" ] && [ -f "$private_key_resolved" ]; then
    key_type=$(stat -Lc %F "$CERTIFICATE_PRIVATE_KEY_PATH")
    key_uid=$(stat -Lc %u "$CERTIFICATE_PRIVATE_KEY_PATH")
    key_mode=$(stat -Lc %a "$CERTIFICATE_PRIVATE_KEY_PATH")
    key_bytes=$(stat -Lc %s "$CERTIFICATE_PRIVATE_KEY_PATH")
    printf 'configured_path=%s\nresolved_path=%s\ntype=%s\nuid=%s\nmode=%s\nbytes=%s\ncontents_read=no\n' \
        "$CERTIFICATE_PRIVATE_KEY_PATH" "$private_key_resolved" "$key_type" "$key_uid" "$key_mode" "$key_bytes" \
        > "$output_dir/certificate-private-key-path-metadata.txt"
    [ "$key_type" = "regular file" ] || fail "resolved private-key target is not a regular file"
    [ "$key_uid" = 0 ] || fail "resolved private-key target is not root-owned"
    case "$key_mode" in
        400|600) : ;;
        *) fail "resolved private-key target mode must be 0400 or 0600" ;;
    esac
    [ "$key_bytes" -gt 0 ] || fail "resolved private-key target is empty"
else
    fail "resolved private-key target is absent"
fi
record certificate_private_key_contents_read no
record certificate_key_pair_match_deferred_to_install yes

if [ ! -f "$TEMPLATE" ]; then
    fail "Apache proposal template is absent"
else
    if ! python3 - "$TEMPLATE" "$output_dir/candidate-apache-fragment.conf" \
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
required = (
    '<LocationMatch "^/outbound-mail/api/v1/status$">',
    '<LocationMatch "^/outbound-mail/api/v1/prepare$">',
    '<Limit GET>',
    '<Limit POST>',
    'Require ip ' + sys.argv[4],
    'http://127.0.0.1:8104/outbound-mail/api/v1/status',
    'http://127.0.0.1:8104/outbound-mail/api/v1/prepare',
)
for item in required:
    if item not in template:
        raise SystemExit(f"candidate is missing required fragment: {item}")
if template.count('Require ip ' + sys.argv[4]) != 2:
    raise SystemExit("candidate must contain exactly two source restrictions")
if "/outbound-mail/send" in template:
    raise SystemExit("candidate contains an unauthorized send route")
if 'LocationMatch "^/outbound-mail/api/v1/.*' in template:
    raise SystemExit("candidate contains a wildcard API location")
out.write_text(template, encoding="utf-8")
PY
    then
        fail "Apache candidate fragment rendering failed"
    fi
fi

record hmac_secret_read no
record proxy_config_installed no
record proxy_service_reloaded no
record certificate_generated no
record dns_modified no
record firewall_modified no
record public_listener_added no
record website_bridge_enabled no
record provider_or_sender_enabled no
record external_delivery_enabled no
record message_sent no

if [ "$failures" -gt 0 ]; then
    readiness_state=not_ready
else
    readiness_state=ready_for_explicit_b2_apache_authorization
fi
record readiness_state "$readiness_state"
record failures "$failures"

(
    cd "$output_dir"
    find . -maxdepth 1 -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
)
chmod -R go-rwx "$output_dir"

cat "$output_dir/summary.txt"
if [ -s "$output_dir/failures.txt" ]; then
    echo "Phase B2 Apache proposal audit failed:" >&2
    cat "$output_dir/failures.txt" >&2
    echo "Evidence: $output_dir" >&2
    exit 1
fi

printf '%s\n' "Phase B2 Apache proposal audit completed."
printf '%s\n' "No HMAC or private-key contents were read, and no Apache, certificate, DNS, firewall, bridge, provider, sender, delivery, or message state was changed."
printf 'Evidence: %s\n' "$output_dir"
printf 'readiness_state=%s\n' "$readiness_state"
