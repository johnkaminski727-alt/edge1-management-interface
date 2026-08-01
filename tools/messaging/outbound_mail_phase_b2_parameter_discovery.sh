#!/bin/sh
set -eu
umask 077

EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
REPO=${REPO:-/opt/edge1-management-interface}
EVIDENCE_ROOT=${EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-parameter-discovery}
PROPOSED_HOSTNAME=${PROPOSED_HOSTNAME:-edge1.ww.cx}
PROPOSED_CLIENT_CIDR=${PROPOSED_CLIENT_CIDR:-}
SERVICE=${SERVICE:-wwcx-outbound-mail-gateway.service}
PORT=${PORT:-8104}
HEALTH_PATH=${HEALTH_PATH:-/outbound-mail/healthz}

failures=0
pending=0

fail() {
    printf '%s\n' "$*" >> "$output_dir/failures.txt"
    failures=$((failures + 1))
}

pend() {
    printf '%s\n' "$*" >> "$output_dir/pending-decisions.txt"
    pending=$((pending + 1))
}

record() {
    printf '%s=%s\n' "$1" "$2" | tee -a "$output_dir/summary.txt"
}

validate_client_cidr() {
    python3 - "$1" <<'PY'
import ipaddress
import sys

value = sys.argv[1]
try:
    network = ipaddress.ip_network(value, strict=True)
except ValueError:
    raise SystemExit(1)
if network.version == 4 and network.prefixlen == 32:
    raise SystemExit(0)
if network.version == 6 and network.prefixlen == 128:
    raise SystemExit(0)
raise SystemExit(1)
PY
}

if [ "$(id -u)" -ne 0 ]; then
    echo "This discovery audit must run as root." >&2
    exit 1
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

stamp=$(date -u +%Y%m%dT%H%M%SZ)
output_dir="$EVIDENCE_ROOT/$stamp"
install -d -m 0700 "$output_dir"
: > "$output_dir/failures.txt"
: > "$output_dir/pending-decisions.txt"
: > "$output_dir/summary.txt"

captured_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
record captured_at "$captured_at"
record host "$host_fqdn"
record principal "$(id -un)"
record repository "$REPO"
record branch "$branch"
record head_commit "$head_commit"
record proposed_hostname "$PROPOSED_HOSTNAME"
if [ -n "$PROPOSED_CLIENT_CIDR" ]; then
    record proposed_client_cidr "$PROPOSED_CLIENT_CIDR"
else
    record proposed_client_cidr not_supplied
fi

if [ "$PROPOSED_HOSTNAME" != edge1.ww.cx ]; then
    fail "proposed hostname must be exactly edge1.ww.cx to match the committed website allow-list"
fi
if [ -n "$PROPOSED_CLIENT_CIDR" ] && ! validate_client_cidr "$PROPOSED_CLIENT_CIDR"; then
    fail "proposed client CIDR must be one exact IPv4 /32 or IPv6 /128"
fi

systemctl is-active "$SERVICE" > "$output_dir/service-active.txt" 2>&1 || fail "$SERVICE is not active"
systemctl is-enabled "$SERVICE" > "$output_dir/service-enabled.txt" 2>&1 || fail "$SERVICE is not enabled"
systemctl show "$SERVICE" -p User -p ActiveState -p SubState -p FragmentPath -p DropInPaths -p EnvironmentFiles > "$output_dir/service-properties.txt" 2>&1 || fail "could not inspect service properties"
ss -lntp > "$output_dir/listeners.txt" 2>&1 || fail "could not capture listeners"
if ! awk -v port=":$PORT" '$4 ~ /127\.0\.0\.1:/ && index($4, port) {found=1} END {exit !found}' "$output_dir/listeners.txt"; then
    fail "gateway listener was not found on 127.0.0.1:$PORT"
fi
if awk -v port=":$PORT" '$4 !~ /127\.0\.0\.1:/ && index($4, port) {found=1} END {exit !found}' "$output_dir/listeners.txt"; then
    fail "gateway port $PORT is exposed beyond IPv4 loopback"
fi

health_http=$(curl -sS -o "$output_dir/health.json" -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT$HEALTH_PATH" 2> "$output_dir/health-error.txt" || printf 000)
record health_path "$HEALTH_PATH"
record health_http "$health_http"
[ "$health_http" = 200 ] || fail "gateway health request did not return HTTP 200"
unsigned_http=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/outbound-mail/api/v1/status" || printf 000)
send_http=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$PORT/outbound-mail/send" || printf 000)
record unsigned_api_status_http "$unsigned_http"
record send_probe_http "$send_http"
[ "$unsigned_http" = 401 ] || fail "unsigned preparation status did not return HTTP 401"
[ "$send_http" = 403 ] || fail "send probe did not return HTTP 403"

{
    echo "# DNS resolution inventory"
    if command -v getent >/dev/null 2>&1; then
        getent ahosts "$PROPOSED_HOSTNAME" || true
    fi
    if command -v dig >/dev/null 2>&1; then
        dig +short A "$PROPOSED_HOSTNAME" || true
        dig +short AAAA "$PROPOSED_HOSTNAME" || true
    fi
} > "$output_dir/dns-resolution.txt" 2>&1

{
    echo "# Port 443 listeners"
    ss -lntp | awk 'NR == 1 || $4 ~ /:443$/' || true
    echo
    echo "# Web service states"
    for unit in nginx.service apache2.service httpd.service caddy.service; do
        if systemctl list-unit-files "$unit" --no-legend 2>/dev/null | grep -q .; then
            printf '%s active=' "$unit"
            systemctl is-active "$unit" 2>/dev/null || true
            printf '%s enabled=' "$unit"
            systemctl is-enabled "$unit" 2>/dev/null || true
        fi
    done
} > "$output_dir/proxy-inventory.txt" 2>&1

config_refs="$output_dir/proxy-certificate-references.txt"
: > "$config_refs"
for root in /etc/nginx /etc/apache2 /etc/httpd /etc/caddy; do
    if [ -d "$root" ]; then
        grep -RInE --include='*.conf' --include='*.vhost' --include='Caddyfile' \
            'edge1\.ww\.cx|ssl_certificate(_key)?|SSLCertificate(File|KeyFile)' "$root" \
            >> "$config_refs" 2>/dev/null || true
    fi
done

active_vhosts="$output_dir/active-edge1-vhosts.txt"
: > "$active_vhosts"
for root in /etc/apache2/sites-enabled /etc/nginx/sites-enabled /etc/nginx/conf.d /etc/httpd/conf.d; do
    [ -d "$root" ] || continue
    find "$root" -maxdepth 2 \( -type f -o -type l \) -print 2>/dev/null |
    while IFS= read -r config; do
        if grep -Eq '(^|[[:space:]])(ServerName|server_name)[[:space:]]+([^;[:space:]]+[[:space:]]+)*edge1\.ww\.cx([;[:space:]]|$)' "$config" 2>/dev/null; then
            printf '%s\n' "$config"
        fi
    done >> "$active_vhosts"
done
sort -u "$active_vhosts" -o "$active_vhosts"

active_refs="$output_dir/active-edge1-certificate-references.txt"
: > "$active_refs"
while IFS= read -r config; do
    [ -n "$config" ] || continue
    printf 'config=%s\n' "$config" >> "$active_refs"
    grep -nE 'SSLCertificate(File|KeyFile)|ssl_certificate(_key)?[[:space:]]' "$config" >> "$active_refs" 2>/dev/null || true
    printf '%s\n' '---' >> "$active_refs"
done < "$active_vhosts"

active_cert_paths="$output_dir/active-certificate-paths.txt"
active_key_paths="$output_dir/active-private-key-paths.txt"
: > "$active_cert_paths"
: > "$active_key_paths"
while IFS= read -r config; do
    [ -n "$config" ] || continue
    sed -nE \
        -e 's/^[[:space:]]*SSLCertificateFile[[:space:]]+([^[:space:]]+).*/\1/p' \
        -e 's/^[[:space:]]*ssl_certificate[[:space:]]+([^;[:space:]]+).*/\1/p' \
        "$config" >> "$active_cert_paths" || true
    sed -nE \
        -e 's/^[[:space:]]*SSLCertificateKeyFile[[:space:]]+([^[:space:]]+).*/\1/p' \
        -e 's/^[[:space:]]*ssl_certificate_key[[:space:]]+([^;[:space:]]+).*/\1/p' \
        "$config" >> "$active_key_paths" || true
done < "$active_vhosts"
sort -u "$active_cert_paths" -o "$active_cert_paths"
sort -u "$active_key_paths" -o "$active_key_paths"
active_vhost_count=$(awk 'NF {count++} END {print count+0}' "$active_vhosts")
active_cert_count=$(awk 'NF {count++} END {print count+0}' "$active_cert_paths")
active_key_count=$(awk 'NF {count++} END {print count+0}' "$active_key_paths")
record active_edge1_vhost_count "$active_vhost_count"
record active_certificate_reference_count "$active_cert_count"
record active_private_key_reference_count "$active_key_count"

cert_candidates="$output_dir/certificate-candidates.txt"
key_metadata="$output_dir/private-key-path-metadata.txt"
: > "$cert_candidates"
: > "$key_metadata"

cert_list="$output_dir/certificate-paths.txt"
: > "$cert_list"
for root in /etc/letsencrypt/live /etc/ssl/certs /var/lib/acme /var/lib/caddy; do
    if [ -d "$root" ]; then
        find "$root" -maxdepth 5 \( -type f -o -type l \) \
            \( -name 'fullchain.pem' -o -name '*.crt' -o -name '*.cer' -o -name 'cert.pem' \) \
            -print >> "$cert_list" 2>/dev/null || true
    fi
done
sort -u "$cert_list" -o "$cert_list"

matching_cert_count=0
while IFS= read -r cert; do
    [ -n "$cert" ] || continue
    {
        echo "path=$cert"
        stat -Lc 'resolved_path=%N owner=%U:%G mode=%a bytes=%s type=%F' "$cert" 2>/dev/null || stat -c 'path_metadata=%N owner=%U:%G mode=%a bytes=%s type=%F' "$cert" 2>/dev/null || true
        if openssl x509 -in "$cert" -noout -subject -issuer -dates -ext subjectAltName > "$output_dir/.cert-info.tmp" 2>/dev/null; then
            cat "$output_dir/.cert-info.tmp"
            if grep -Eq 'DNS:edge1\.ww\.cx([,[:space:]]|$)|DNS:\*\.ww\.cx([,[:space:]]|$)' "$output_dir/.cert-info.tmp"; then
                echo "covers_edge1_ww_cx=yes"
                matching_cert_count=$((matching_cert_count + 1))
            else
                echo "covers_edge1_ww_cx=no"
            fi
        else
            echo "public_certificate_parse=failed"
        fi
        echo "---"
    } >> "$cert_candidates"
done < "$cert_list"
rm -f "$output_dir/.cert-info.tmp"

key_paths="$output_dir/private-key-paths.txt"
: > "$key_paths"
if [ -s "$config_refs" ]; then
    sed -nE \
        -e 's/.*ssl_certificate_key[[:space:]]+([^;[:space:]]+).*/\1/p' \
        -e 's/.*SSLCertificateKeyFile[[:space:]]+([^[:space:]]+).*/\1/p' \
        "$config_refs" >> "$key_paths" || true
fi
sort -u "$key_paths" -o "$key_paths"

existing_key_count=0
while IFS= read -r key; do
    [ -n "$key" ] || continue
    echo "path=$key" >> "$key_metadata"
    if [ -e "$key" ]; then
        stat -Lc 'resolved_path=%N owner=%U:%G mode=%a bytes=%s type=%F contents_read=no' "$key" >> "$key_metadata" 2>/dev/null \
            || stat -c 'path_metadata=%N owner=%U:%G mode=%a bytes=%s type=%F contents_read=no' "$key" >> "$key_metadata" 2>/dev/null \
            || true
        existing_key_count=$((existing_key_count + 1))
    else
        echo "present=no contents_read=no" >> "$key_metadata"
    fi
    echo "---" >> "$key_metadata"
done < "$key_paths"

active_cert_path=""
active_key_path=""
active_cert_valid=no
active_key_valid=no
active_cert_metadata="$output_dir/active-certificate-metadata.txt"
active_key_metadata="$output_dir/active-private-key-path-metadata.txt"
: > "$active_cert_metadata"
: > "$active_key_metadata"

if [ "$active_cert_count" -eq 1 ]; then
    active_cert_path=$(sed -n '1p' "$active_cert_paths")
    echo "path=$active_cert_path" >> "$active_cert_metadata"
    if [ -f "$active_cert_path" ] && openssl x509 -in "$active_cert_path" -noout -subject -issuer -dates -ext subjectAltName > "$output_dir/.active-cert-info.tmp" 2>/dev/null; then
        cat "$output_dir/.active-cert-info.tmp" >> "$active_cert_metadata"
        if grep -Eq 'DNS:edge1\.ww\.cx([,[:space:]]|$)|DNS:\*\.ww\.cx([,[:space:]]|$)' "$output_dir/.active-cert-info.tmp"; then
            active_cert_valid=yes
            echo "covers_edge1_ww_cx=yes" >> "$active_cert_metadata"
        else
            echo "covers_edge1_ww_cx=no" >> "$active_cert_metadata"
            fail "active certificate reference does not cover edge1.ww.cx"
        fi
    else
        echo "public_certificate_parse=failed" >> "$active_cert_metadata"
        fail "active certificate reference could not be parsed"
    fi
else
    pend "enabled edge1.ww.cx vhost did not resolve to exactly one certificate path"
fi
rm -f "$output_dir/.active-cert-info.tmp"

if [ "$active_key_count" -eq 1 ]; then
    active_key_path=$(sed -n '1p' "$active_key_paths")
    echo "path=$active_key_path" >> "$active_key_metadata"
    if [ -e "$active_key_path" ]; then
        stat -Lc 'resolved_path=%N owner=%U:%G mode=%a bytes=%s type=%F contents_read=no' "$active_key_path" >> "$active_key_metadata" 2>/dev/null \
            || stat -c 'path_metadata=%N owner=%U:%G mode=%a bytes=%s type=%F contents_read=no' "$active_key_path" >> "$active_key_metadata" 2>/dev/null \
            || true
        active_key_mode=$(stat -Lc '%a' "$active_key_path" 2>/dev/null || stat -c '%a' "$active_key_path" 2>/dev/null || printf unknown)
        case "$active_key_mode" in
            400|600) active_key_valid=yes ;;
            *) fail "active private-key path mode must be 0400 or 0600" ;;
        esac
    else
        echo "present=no contents_read=no" >> "$active_key_metadata"
        fail "active private-key path does not exist"
    fi
else
    pend "enabled edge1.ww.cx vhost did not resolve to exactly one private-key path"
fi

record matching_certificate_candidates "$matching_cert_count"
record existing_private_key_path_candidates "$existing_key_count"
record active_certificate_valid "$active_cert_valid"
record active_private_key_path_valid "$active_key_valid"
record active_tls_pair_in_enabled_vhost "$([ "$active_cert_valid" = yes ] && [ "$active_key_valid" = yes ] && printf yes || printf no)"
record private_key_contents_read no
record hmac_secret_read no
record proxy_config_installed no
record proxy_service_reloaded no
record certificate_generated no
record dns_modified no
record firewall_modified no
record public_listener_added no
record website_bridge_enabled no
record provider_or_sender_enabled no
record message_sent no

proposal="$output_dir/candidate-parameters.env"
{
    printf "PROPOSED_HOSTNAME='%s'\n" "$PROPOSED_HOSTNAME"
    if [ -n "$PROPOSED_CLIENT_CIDR" ]; then
        printf "PROPOSED_CLIENT_CIDR='%s'\n" "$PROPOSED_CLIENT_CIDR"
    else
        printf "PROPOSED_CLIENT_CIDR='BUSINESS159_EGRESS_MEASUREMENT_REQUIRED'\n"
    fi
    if [ "$active_cert_valid" = yes ]; then
        printf "CERTIFICATE_FULLCHAIN_PATH='%s'\n" "$active_cert_path"
    else
        printf "CERTIFICATE_FULLCHAIN_PATH='SELECTION_REQUIRED'\n"
    fi
    if [ "$active_key_valid" = yes ]; then
        printf "CERTIFICATE_PRIVATE_KEY_PATH='%s'\n" "$active_key_path"
    else
        printf "CERTIFICATE_PRIVATE_KEY_PATH='SELECTION_REQUIRED'\n"
    fi
} > "$proposal"

if [ -z "$PROPOSED_CLIENT_CIDR" ]; then
    pend "measure the actual business159 outbound NAT address and supply one exact /32 or /128"
fi

if [ "$failures" -gt 0 ]; then
    readiness_state=not_ready
elif [ "$active_cert_valid" = yes ] && [ "$active_key_valid" = yes ] && [ -n "$PROPOSED_CLIENT_CIDR" ]; then
    readiness_state=ready_for_phase_b2_proposal_validation
elif [ "$active_cert_valid" = yes ] && [ "$active_key_valid" = yes ]; then
    readiness_state=awaiting_business159_egress_measurement
else
    readiness_state=awaiting_active_certificate_selection_and_business159_egress_measurement
fi
record readiness_state "$readiness_state"
record failures "$failures"
record pending_decisions "$pending"

(
    cd "$output_dir"
    find . -maxdepth 1 -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
)

printf '%s\n' "Phase B2 Edge1 parameter discovery completed."
printf '%s\n' "No HMAC or private-key contents were read, and no proxy, certificate, DNS, firewall, listener, provider, sender, delivery, or message state was changed."
printf 'Evidence: %s\n' "$output_dir"
printf 'readiness_state=%s\n' "$readiness_state"

[ "$failures" -eq 0 ]
