#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CERT_SOURCE=${WWCX_NTS_CERT_SOURCE:-}
KEY_SOURCE=${WWCX_NTS_KEY_SOURCE:-}
LIVE_CONF=${WWCX_NTS_CHRONY_CONF:-/etc/chrony/chrony.conf}
PUBLIC_IP=${WWCX_NTP_PUBLIC_IPV4:-89.147.109.253}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root so certificate/key metadata can be validated without exposing contents"

for cmd in chronyd chronyc openssl systemctl ss getent awk grep cmp mktemp; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done

[ -n "$CERT_SOURCE" ] || fail "set WWCX_NTS_CERT_SOURCE to the reviewed PEM full-chain certificate for ntp.ww.cx"
[ -n "$KEY_SOURCE" ] || fail "set WWCX_NTS_KEY_SOURCE to the matching unencrypted PEM private key"
[ -r "$CERT_SOURCE" ] || fail "certificate source is not readable: $CERT_SOURCE"
[ -r "$KEY_SOURCE" ] || fail "private-key source is not readable: $KEY_SOURCE"
[ -r "$LIVE_CONF" ] || fail "chrony configuration is not readable: $LIVE_CONF"

systemctl is-active --quiet chrony.service || fail "chrony.service is not active"

if ! chronyd -v 2>&1 | grep -q '+NTS'; then
  fail "installed chronyd does not report +NTS support"
fi

if ! openssl x509 -in "$CERT_SOURCE" -noout -checkhost ntp.ww.cx >/dev/null 2>&1; then
  fail "certificate does not validate the hostname ntp.ww.cx"
fi
if ! openssl x509 -in "$CERT_SOURCE" -noout -checkend 604800 >/dev/null 2>&1; then
  fail "certificate expires within 7 days"
fi

openssl x509 -in "$CERT_SOURCE" -pubkey -noout > "$tmp/cert-public.pem" 2>/dev/null || \
  fail "could not extract certificate public key"
openssl pkey -pubin -in "$tmp/cert-public.pem" -outform DER > "$tmp/cert-public.der" 2>/dev/null || \
  fail "could not normalize certificate public key"
openssl pkey -in "$KEY_SOURCE" -passin pass: -pubout -outform DER > "$tmp/key-public.der" 2>/dev/null || \
  fail "private key is unreadable, encrypted, or unsupported; chronyd requires unattended key access"
cmp -s "$tmp/cert-public.der" "$tmp/key-public.der" || fail "certificate and private key do not match"

if ! getent ahostsv4 ntp.ww.cx | awk '{print $1}' | grep -Fxq "$PUBLIC_IP"; then
  fail "ntp.ww.cx does not resolve locally to expected IPv4 $PUBLIC_IP"
fi

if [ -z "$(ss -H -lun 'sport = :123' 2>/dev/null)" ]; then
  fail "chronyd is not listening on UDP/123"
fi

TCP4460=$(ss -H -ltnp 'sport = :4460' 2>/dev/null || true)
if [ -n "$TCP4460" ]; then
  printf '%s\n' "$TCP4460" | grep -q 'chronyd' || fail "TCP/4460 is already owned by a non-chronyd service"
  echo "NOTICE: TCP/4460 is already owned by chronyd; treat this as an NTS update/revalidation."
else
  echo "PASS: TCP/4460 is currently free."
fi

chronyd -p -f "$LIVE_CONF" >/dev/null 2> "$tmp/chronyd-parse.err" || {
  cat "$tmp/chronyd-parse.err" >&2
  fail "current chrony configuration does not parse"
}

chronyc tracking
chronyc sources -v
sh "$ROOT/deploy/time-authority-ntp-server-edge1-smoke-test.sh"

openssl x509 -in "$CERT_SOURCE" -noout -subject -issuer -dates -ext subjectAltName

echo "WW.CX NTS Edge1 preflight passed."
echo "No certificate, chrony configuration, service, firewall, DNS, or listener changes were made."
