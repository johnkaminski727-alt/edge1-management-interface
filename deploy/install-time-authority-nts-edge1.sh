#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CERT_SOURCE=${WWCX_NTS_CERT_SOURCE:-}
KEY_SOURCE=${WWCX_NTS_KEY_SOURCE:-}
LIVE_CONF=${WWCX_NTS_CHRONY_CONF:-/etc/chrony/chrony.conf}
FRAGMENT_SOURCE="$ROOT/modules/time-authority/config/edge1-chrony-nts.conf"
FRAGMENT_TARGET=${WWCX_NTS_FRAGMENT_TARGET:-/etc/chrony/conf.d/wwcx-nts.conf}
NTS_DIR=${WWCX_NTS_DIR:-/etc/chrony/nts}
TARGET_CERT="$NTS_DIR/ntp.ww.cx-fullchain.pem"
TARGET_KEY="$NTS_DIR/ntp.ww.cx-privkey.pem"
EVIDENCE_ROOT=${WWCX_NTP_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/public-ntp-server}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/nts-$STAMP"
MUTATED=0

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

rollback_and_fail() {
  message=$1
  if [ "$MUTATED" -eq 1 ]; then
    cp -a "$EVIDENCE_DIR/chrony.conf.before" "$LIVE_CONF" 2>/dev/null || true
    rm -f "$FRAGMENT_TARGET" "$TARGET_CERT" "$TARGET_KEY"
    systemctl restart chrony.service >/dev/null 2>&1 || true
    sh "$ROOT/deploy/time-authority-ntp-server-edge1-smoke-test.sh" >/dev/null 2>&1 || true
  fi
  fail "$message; current-run NTS changes were rolled back where possible; evidence: $EVIDENCE_DIR"
}

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root"
[ "${WWCX_NTS_APPROVE_CERTIFICATE_INSTALL:-}" = "YES" ] || \
  fail "set WWCX_NTS_APPROVE_CERTIFICATE_INSTALL=YES only after explicit approval to install the NTS certificate/private key"
[ "${WWCX_NTS_APPROVE_NTS_LISTENER:-}" = "YES" ] || \
  fail "set WWCX_NTS_APPROVE_NTS_LISTENER=YES only after explicit approval to activate chronyd NTS-KE on TCP/4460"

[ -n "$CERT_SOURCE" ] || fail "WWCX_NTS_CERT_SOURCE is required"
[ -n "$KEY_SOURCE" ] || fail "WWCX_NTS_KEY_SOURCE is required"
[ -r "$FRAGMENT_SOURCE" ] || fail "missing reviewed NTS fragment: $FRAGMENT_SOURCE"

# This first-activation installer never overwrites an existing NTS private key.
# Certificate renewal/update needs a separate reviewed rotation procedure.
[ ! -e "$TARGET_CERT" ] || fail "target NTS certificate already exists; refusing to overwrite an existing certificate lifecycle"
[ ! -e "$TARGET_KEY" ] || fail "target NTS private key already exists; refusing to overwrite an existing private key"
[ ! -e "$FRAGMENT_TARGET" ] || fail "NTS chrony fragment already exists; review current NTS state before changing it"

WWCX_NTS_CERT_SOURCE="$CERT_SOURCE" \
WWCX_NTS_KEY_SOURCE="$KEY_SOURCE" \
WWCX_NTS_CHRONY_CONF="$LIVE_CONF" \
  sh "$ROOT/deploy/time-authority-nts-edge1-preflight.sh"

for cmd in install cp rm ps id awk grep chronyd chronyc systemctl ss git stat; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done

CHRONY_USER=$(ps -eo user=,comm= | awk '$2 == "chronyd" && NF {print $1; exit}')
[ -n "$CHRONY_USER" ] || fail "could not determine the effective chronyd user"
CHRONY_GROUP=$(id -gn "$CHRONY_USER")
[ -n "$CHRONY_GROUP" ] || fail "could not determine the effective chronyd group"

install -d -m 0750 "$EVIDENCE_DIR"
cp -a "$LIVE_CONF" "$EVIDENCE_DIR/chrony.conf.before"
{
  echo "timestamp_utc=$STAMP"
  echo "repo_root=$ROOT"
  printf 'repo_head='
  git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown
  echo "certificate_source_path=$CERT_SOURCE"
  echo "private_key_source_path=$KEY_SOURCE"
  echo "chronyd_user=$CHRONY_USER"
  echo "chronyd_group=$CHRONY_GROUP"
} > "$EVIDENCE_DIR/install-metadata.txt"
(systemctl status chrony.service --no-pager 2>&1 || true) > "$EVIDENCE_DIR/chrony-status.before.txt"
(chronyc tracking 2>&1 || true) > "$EVIDENCE_DIR/chrony-tracking.before.txt"
(ss -H -ltnp 'sport = :4460' 2>&1 || true) > "$EVIDENCE_DIR/tcp4460.before.txt"
openssl x509 -in "$CERT_SOURCE" -noout -subject -issuer -dates -ext subjectAltName > "$EVIDENCE_DIR/certificate-public-metadata.txt"
stat -Lc 'source_key_path=%n owner=%U:%G mode=%a bytes=%s contents_recorded=no' "$KEY_SOURCE" > "$EVIDENCE_DIR/private-key-metadata.txt" 2>/dev/null || true

install -d -m 0755 /etc/chrony/conf.d || rollback_and_fail "could not create chrony fragment directory"
install -d -o root -g "$CHRONY_GROUP" -m 0750 "$NTS_DIR" || rollback_and_fail "could not create NTS credential directory"
install -o root -g "$CHRONY_GROUP" -m 0640 "$CERT_SOURCE" "$TARGET_CERT" || rollback_and_fail "could not stage NTS certificate"
install -o root -g "$CHRONY_GROUP" -m 0640 "$KEY_SOURCE" "$TARGET_KEY" || rollback_and_fail "could not stage NTS private key"
install -o root -g root -m 0644 "$FRAGMENT_SOURCE" "$FRAGMENT_TARGET" || rollback_and_fail "could not install NTS chrony fragment"
MUTATED=1

if ! grep -Fqx 'confdir /etc/chrony/conf.d' "$LIVE_CONF"; then
  {
    printf '\n# Optional reviewed WW.CX service fragments.\n'
    printf 'confdir /etc/chrony/conf.d\n'
  } >> "$LIVE_CONF" || rollback_and_fail "could not enable chrony fragment directory"
fi

if ! chronyd -p -f "$LIVE_CONF" > "$EVIDENCE_DIR/chrony-expanded-config.txt" 2> "$EVIDENCE_DIR/chrony-parse-error.txt"; then
  rollback_and_fail "chrony configuration failed syntax validation"
fi

if ! systemctl restart chrony.service; then
  rollback_and_fail "chrony.service failed to restart with NTS enabled"
fi

if ! chronyc waitsync 30 0 0 2; then
  rollback_and_fail "chronyd did not return to synchronized state after NTS activation"
fi

if ! sh "$ROOT/deploy/time-authority-nts-edge1-smoke-test.sh"; then
  rollback_and_fail "local NTS-KE/NTP smoke test failed"
fi

(systemctl status chrony.service --no-pager 2>&1 || true) > "$EVIDENCE_DIR/chrony-status.after.txt"
(chronyc tracking 2>&1 || true) > "$EVIDENCE_DIR/chrony-tracking.after.txt"
(chronyc sources -v 2>&1 || true) > "$EVIDENCE_DIR/chrony-sources.after.txt"
(ss -H -ltnp 'sport = :4460' 2>&1 || true) > "$EVIDENCE_DIR/tcp4460.after.txt"
(ss -H -lunp 'sport = :123' 2>&1 || true) > "$EVIDENCE_DIR/udp123.after.txt"
stat -Lc 'target_key_path=%n owner=%U:%G mode=%a bytes=%s contents_recorded=no' "$TARGET_KEY" >> "$EVIDENCE_DIR/private-key-metadata.txt" 2>/dev/null || true

printf '%s\n' \
  "WW.CX Edge1 NTS-KE activated locally." \
  "Canonical NTS hostname: ntp.ww.cx" \
  "NTS-KE listener: TCP/4460" \
  "Standard NTP UDP/123 revalidated." \
  "Perimeter TCP/4460 firewall publication is NOT performed by this installer." \
  "Rollback evidence: $EVIDENCE_DIR"
