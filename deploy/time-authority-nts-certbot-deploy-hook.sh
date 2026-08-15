#!/bin/sh
set -eu

EXPECTED_LINEAGE=${WWCX_NTS_CERTBOT_LINEAGE:-/etc/letsencrypt/live/ntp.ww.cx}
NTS_DIR=${WWCX_NTS_DIR:-/etc/chrony/nts}
TARGET_CERT="$NTS_DIR/ntp.ww.cx-fullchain.pem"
TARGET_KEY="$NTS_DIR/ntp.ww.cx-privkey.pem"
FRAGMENT_TARGET=${WWCX_NTS_FRAGMENT_TARGET:-/etc/chrony/conf.d/wwcx-nts.conf}
EVIDENCE_ROOT=${WWCX_NTP_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/public-ntp-server}
LINEAGE=${RENEWED_LINEAGE:-}

# Certbot may run directory hooks for unrelated lineages. Ignore all of them.
[ "$LINEAGE" = "$EXPECTED_LINEAGE" ] || exit 0

SOURCE_CERT="$LINEAGE/fullchain.pem"
SOURCE_KEY="$LINEAGE/privkey.pem"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/nts-renewal-$STAMP"
BACKUP_CERT="$EVIDENCE_DIR/ntp.ww.cx-fullchain.before.pem"
BACKUP_KEY="$EVIDENCE_DIR/ntp.ww.cx-privkey.before.pem"
MUTATED=0

fail() {
  echo "WW.CX NTS renewal hook FAIL: $*" >&2
  exit 1
}

hostname_matches() {
  cert=$1
  host=$2
  set +e
  output=$(openssl x509 -in "$cert" -noout -checkhost "$host" 2>&1)
  rc=$?
  set -e
  case "$output" in
    *"does match certificate"*) return 0 ;;
    *"does NOT match certificate"*) return 1 ;;
  esac
  [ "$rc" -ne 0 ] && return 1
  return 2
}

rollback_and_fail() {
  message=$1
  if [ "$MUTATED" -eq 1 ]; then
    [ -f "$BACKUP_CERT" ] && cp -a "$BACKUP_CERT" "$TARGET_CERT" || true
    [ -f "$BACKUP_KEY" ] && cp -a "$BACKUP_KEY" "$TARGET_KEY" || true
    systemctl restart chrony.service >/dev/null 2>&1 || true
  fi
  fail "$message; previous staged NTS credentials restored where possible; evidence: $EVIDENCE_DIR"
}

[ "$(id -u)" -eq 0 ] || fail "hook must run as root"
for cmd in openssl systemctl chronyc ss install cp mv mktemp ps id awk grep stat cmp rm date; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done

[ -r "$SOURCE_CERT" ] || fail "renewed certificate is not readable: $SOURCE_CERT"
[ -r "$SOURCE_KEY" ] || fail "renewed private key is not readable: $SOURCE_KEY"
[ -r "$TARGET_CERT" ] || fail "staged chronyd certificate is missing: $TARGET_CERT"
[ -r "$TARGET_KEY" ] || fail "staged chronyd private key is missing: $TARGET_KEY"
[ -r "$FRAGMENT_TARGET" ] || fail "NTS chrony fragment is missing: $FRAGMENT_TARGET"
systemctl is-active --quiet chrony.service || fail "chrony.service is not active"

hostname_matches "$SOURCE_CERT" ntp.ww.cx || fail "renewed certificate does not validate ntp.ww.cx"
openssl x509 -in "$SOURCE_CERT" -noout -checkend 604800 >/dev/null 2>&1 || fail "renewed certificate expires within 7 days"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM
openssl x509 -in "$SOURCE_CERT" -pubkey -noout > "$TMP_DIR/cert-public.pem" 2>/dev/null || fail "could not read renewed certificate public key"
openssl pkey -in "$SOURCE_KEY" -pubout > "$TMP_DIR/key-public.pem" 2>/dev/null || fail "could not read renewed private-key public component"
cmp -s "$TMP_DIR/cert-public.pem" "$TMP_DIR/key-public.pem" || fail "renewed certificate/private key do not match"

CHRONY_USER=$(ps -eo user=,comm= | awk '$2 == "chronyd" && NF {print $1; exit}')
[ -n "$CHRONY_USER" ] || fail "could not determine chronyd user"
CHRONY_GROUP=$(id -gn "$CHRONY_USER")
[ -n "$CHRONY_GROUP" ] || fail "could not determine chronyd group"

install -d -m 0750 "$EVIDENCE_DIR"
cp -a "$TARGET_CERT" "$BACKUP_CERT"
cp -a "$TARGET_KEY" "$BACKUP_KEY"
openssl x509 -in "$SOURCE_CERT" -noout -subject -issuer -dates -ext subjectAltName > "$EVIDENCE_DIR/renewed-certificate-public-metadata.txt"
stat -Lc 'renewed_key_path=%n owner=%U:%G mode=%a bytes=%s contents_recorded=no' "$SOURCE_KEY" > "$EVIDENCE_DIR/renewed-private-key-metadata.txt" 2>/dev/null || true
(systemctl status chrony.service --no-pager 2>&1 || true) > "$EVIDENCE_DIR/chrony-status.before.txt"

NEW_CERT="$NTS_DIR/.ntp.ww.cx-fullchain.pem.new"
NEW_KEY="$NTS_DIR/.ntp.ww.cx-privkey.pem.new"
rm -f "$NEW_CERT" "$NEW_KEY"
install -o root -g "$CHRONY_GROUP" -m 0640 "$SOURCE_CERT" "$NEW_CERT" || fail "could not stage renewed certificate"
install -o root -g "$CHRONY_GROUP" -m 0640 "$SOURCE_KEY" "$NEW_KEY" || { rm -f "$NEW_CERT"; fail "could not stage renewed private key"; }
MUTATED=1
mv -f "$NEW_CERT" "$TARGET_CERT" || rollback_and_fail "could not atomically replace staged certificate"
mv -f "$NEW_KEY" "$TARGET_KEY" || rollback_and_fail "could not atomically replace staged private key"

systemctl restart chrony.service || rollback_and_fail "chrony.service restart failed after renewed credentials were staged"
chronyc waitsync 30 0 0 2 || rollback_and_fail "chronyd did not resynchronize after renewed credentials were staged"

UDP_LISTENER=$(ss -H -lunp 'sport = :123' 2>/dev/null || true)
[ -n "$UDP_LISTENER" ] || rollback_and_fail "UDP/123 listener disappeared after renewal"
printf '%s\n' "$UDP_LISTENER" | grep -q 'chronyd' || rollback_and_fail "UDP/123 is not owned by chronyd after renewal"
TCP_LISTENER=$(ss -H -ltnp 'sport = :4460' 2>/dev/null || true)
[ -n "$TCP_LISTENER" ] || rollback_and_fail "TCP/4460 listener disappeared after renewal"
printf '%s\n' "$TCP_LISTENER" | grep -q 'chronyd' || rollback_and_fail "TCP/4460 is not owned by chronyd after renewal"

set +e
TLS_OUTPUT=$(openssl s_client -connect 127.0.0.1:4460 -servername ntp.ww.cx -alpn ntske/1 -verify_return_error </dev/null 2>&1)
TLS_RC=$?
set -e
printf '%s\n' "$TLS_OUTPUT" > "$EVIDENCE_DIR/nts-tls-smoke.txt"
[ "$TLS_RC" -eq 0 ] || rollback_and_fail "local NTS-KE TLS verification failed after renewal"
printf '%s\n' "$TLS_OUTPUT" | grep -Fq 'ALPN protocol: ntske/1' || rollback_and_fail "local NTS-KE ALPN smoke test failed after renewal"
printf '%s\n' "$TLS_OUTPUT" | grep -Fq 'Verify return code: 0 (ok)' || rollback_and_fail "local NTS-KE trust result was not clean after renewal"

(systemctl status chrony.service --no-pager 2>&1 || true) > "$EVIDENCE_DIR/chrony-status.after.txt"
(chronyc tracking 2>&1 || true) > "$EVIDENCE_DIR/chrony-tracking.after.txt"
(ss -H -lunp 'sport = :123' 2>&1 || true) > "$EVIDENCE_DIR/udp123.after.txt"
(ss -H -ltnp 'sport = :4460' 2>&1 || true) > "$EVIDENCE_DIR/tcp4460.after.txt"

printf '%s\n' \
  "WW.CX chronyd NTS credentials refreshed from Certbot lineage $LINEAGE." \
  "Standard NTP and local NTS-KE checks passed." \
  "Evidence: $EVIDENCE_DIR"
