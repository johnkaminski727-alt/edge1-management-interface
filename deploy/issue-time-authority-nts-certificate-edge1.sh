#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
HOSTNAME_TO_ISSUE=${WWCX_NTS_HOSTNAME:-ntp.ww.cx}
CERT_NAME=${WWCX_NTS_CERT_NAME:-ntp.ww.cx}
PUBLIC_IP=${WWCX_NTP_PUBLIC_IPV4:-89.147.109.253}
EVIDENCE_ROOT=${WWCX_NTP_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/public-ntp-server}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/nts-certificate-$STAMP"
CERT_PATH="/etc/letsencrypt/live/$CERT_NAME/fullchain.pem"
KEY_PATH="/etc/letsencrypt/live/$CERT_NAME/privkey.pem"
HOST_MATCH_HELPER="$ROOT/tools/time_authority/certificate-matches-hostname.sh"
DISCOVERY_HELPER="$ROOT/tools/time_authority/discover-nts-certificate-edge1.sh"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root"
[ "${WWCX_NTS_APPROVE_CERTIFICATE_ISSUANCE:-}" = "YES" ] || \
  fail "set WWCX_NTS_APPROVE_CERTIFICATE_ISSUANCE=YES only after explicit approval to request a dedicated public certificate for ntp.ww.cx"

for cmd in certbot openssl getent systemctl ss install cp git awk grep cmp apache2ctl mktemp stat rm date; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done
[ -r "$HOST_MATCH_HELPER" ] || fail "hostname-match helper is missing: $HOST_MATCH_HELPER"
[ -r "$DISCOVERY_HELPER" ] || fail "certificate discovery helper is missing: $DISCOVERY_HELPER"

[ "$HOSTNAME_TO_ISSUE" = "ntp.ww.cx" ] || fail "this first-issuance helper is restricted to ntp.ww.cx"
[ "$CERT_NAME" = "ntp.ww.cx" ] || fail "this first-issuance helper requires the dedicated certificate name ntp.ww.cx"

systemctl is-active --quiet chrony.service || fail "chrony.service is not active"
systemctl is-active --quiet apache2.service || fail "apache2.service is not active"

if ! getent ahostsv4 "$HOSTNAME_TO_ISSUE" | awk '{print $1}' | grep -Fxq "$PUBLIC_IP"; then
  fail "$HOSTNAME_TO_ISSUE does not resolve locally to reviewed IPv4 $PUBLIC_IP"
fi

HTTP_LISTENER=$(ss -H -ltnp 'sport = :80' 2>/dev/null || true)
[ -n "$HTTP_LISTENER" ] || fail "nothing is listening on TCP/80 for ACME HTTP-01 validation"
printf '%s\n' "$HTTP_LISTENER" | grep -q 'apache2' || fail "TCP/80 is not owned by apache2"

sh "$ROOT/deploy/time-authority-ntp-server-edge1-smoke-test.sh"

set +e
DISCOVERY_OUTPUT=$(sh "$DISCOVERY_HELPER" 2>&1)
DISCOVERY_RC=$?
set -e
if [ "$DISCOVERY_RC" -eq 0 ]; then
  printf '%s\n' "$DISCOVERY_OUTPUT" >&2
  fail "an existing certificate already covers ntp.ww.cx; first-issuance path is not appropriate"
fi
[ "$DISCOVERY_RC" -eq 2 ] || {
  printf '%s\n' "$DISCOVERY_OUTPUT" >&2
  fail "existing-certificate discovery returned unexpected status $DISCOVERY_RC"
}

[ ! -e "/etc/letsencrypt/live/$CERT_NAME" ] || \
  fail "Certbot lineage /etc/letsencrypt/live/$CERT_NAME already exists; manual review required"

install -d -m 0750 "$EVIDENCE_DIR"
{
  echo "timestamp_utc=$STAMP"
  echo "hostname=$HOSTNAME_TO_ISSUE"
  echo "certificate_name=$CERT_NAME"
  echo "public_ipv4=$PUBLIC_IP"
  printf 'repo_head='
  git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown
} > "$EVIDENCE_DIR/issuance-metadata.txt"
(certbot certificates 2>&1 || true) > "$EVIDENCE_DIR/certbot-certificates.before.txt"
(apache2ctl -S 2>&1 || true) > "$EVIDENCE_DIR/apache-vhosts.before.txt"
(getent ahostsv4 "$HOSTNAME_TO_ISSUE" 2>&1 || true) > "$EVIDENCE_DIR/dns.before.txt"
(ss -H -ltnp 'sport = :80' 2>&1 || true) > "$EVIDENCE_DIR/tcp80.before.txt"

# Use the already configured ACME account and Apache authenticator.  Do not pass
# --agree-tos here: if the existing account cannot issue non-interactively under
# its current terms, Certbot must fail rather than accepting new terms implicitly.
if ! certbot certonly \
    --apache \
    --non-interactive \
    --cert-name "$CERT_NAME" \
    --key-type ecdsa \
    -d "$HOSTNAME_TO_ISSUE"; then
  fail "Certbot did not issue the dedicated ntp.ww.cx certificate; no chrony/NTS/firewall changes were attempted; evidence: $EVIDENCE_DIR"
fi

[ -r "$CERT_PATH" ] || fail "issued full chain is not readable at $CERT_PATH"
[ -r "$KEY_PATH" ] || fail "issued private key is not readable at $KEY_PATH"

if ! sh "$HOST_MATCH_HELPER" "$CERT_PATH" "$HOSTNAME_TO_ISSUE" >/dev/null 2>&1; then
  fail "issued certificate does not validate ntp.ww.cx; lineage was preserved for manual review; evidence: $EVIDENCE_DIR"
fi
if ! openssl x509 -in "$CERT_PATH" -noout -checkend 604800 >/dev/null 2>&1; then
  fail "issued certificate expires within 7 days; lineage was preserved for manual review; evidence: $EVIDENCE_DIR"
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM
openssl x509 -in "$CERT_PATH" -pubkey -noout > "$TMP_DIR/cert-public.pem" 2>/dev/null || fail "could not read certificate public key"
openssl pkey -in "$KEY_PATH" -pubout > "$TMP_DIR/key-public.pem" 2>/dev/null || fail "could not read private-key public component"
cmp -s "$TMP_DIR/cert-public.pem" "$TMP_DIR/key-public.pem" || fail "issued certificate/private key do not match"

openssl x509 -in "$CERT_PATH" -noout -subject -issuer -dates -ext subjectAltName > "$EVIDENCE_DIR/certificate-public-metadata.txt"
stat -Lc 'private_key_path=%n owner=%U:%G mode=%a bytes=%s contents_recorded=no' "$KEY_PATH" > "$EVIDENCE_DIR/private-key-metadata.txt" 2>/dev/null || true
(certbot certificates 2>&1 || true) > "$EVIDENCE_DIR/certbot-certificates.after.txt"

printf '%s\n' \
  "Dedicated Let's Encrypt certificate issued for ntp.ww.cx." \
  "Certificate lineage: /etc/letsencrypt/live/ntp.ww.cx" \
  "Certificate was NOT installed into chronyd by this helper." \
  "TCP/4460 firewall state was NOT changed." \
  "Evidence: $EVIDENCE_DIR"
