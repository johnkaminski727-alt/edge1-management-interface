#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$ROOT/deploy/time-authority-nts-certbot-deploy-hook.sh"
TARGET=${WWCX_NTS_CERTBOT_DEPLOY_HOOK:-/etc/letsencrypt/renewal-hooks/deploy/50-wwcx-ntp-chrony-nts}
LINEAGE=${WWCX_NTS_CERTBOT_LINEAGE:-/etc/letsencrypt/live/ntp.ww.cx}
NTS_DIR=${WWCX_NTS_DIR:-/etc/chrony/nts}
FRAGMENT_TARGET=${WWCX_NTS_FRAGMENT_TARGET:-/etc/chrony/conf.d/wwcx-nts.conf}
EVIDENCE_ROOT=${WWCX_NTP_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/public-ntp-server}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/nts-renewal-hook-$STAMP"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root"
[ "${WWCX_NTS_APPROVE_RENEWAL_HOOK_INSTALL:-}" = "YES" ] || \
  fail "set WWCX_NTS_APPROVE_RENEWAL_HOOK_INSTALL=YES only after explicit approval to install the Certbot-to-chronyd NTS renewal deploy hook"

for cmd in install systemctl ss grep sh stat git; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done
[ -r "$SOURCE" ] || fail "reviewed deploy hook source is missing: $SOURCE"
[ -r "$LINEAGE/fullchain.pem" ] || fail "dedicated ntp.ww.cx Certbot lineage is missing"
[ -r "$LINEAGE/privkey.pem" ] || fail "dedicated ntp.ww.cx Certbot private key is missing"
[ -r "$NTS_DIR/ntp.ww.cx-fullchain.pem" ] || fail "chronyd NTS certificate has not been staged yet"
[ -r "$NTS_DIR/ntp.ww.cx-privkey.pem" ] || fail "chronyd NTS private key has not been staged yet"
[ -r "$FRAGMENT_TARGET" ] || fail "chronyd NTS fragment has not been installed yet"
systemctl is-active --quiet chrony.service || fail "chrony.service is not active"

LISTENER=$(ss -H -ltnp 'sport = :4460' 2>/dev/null || true)
[ -n "$LISTENER" ] || fail "chronyd NTS-KE listener is not active on TCP/4460"
printf '%s\n' "$LISTENER" | grep -q 'chronyd' || fail "TCP/4460 is not owned by chronyd"

[ ! -e "$TARGET" ] || fail "renewal hook already exists at $TARGET; manual review required before replacement"

install -d -m 0755 "$(dirname "$TARGET")"
install -d -m 0750 "$EVIDENCE_DIR"
{
  echo "timestamp_utc=$STAMP"
  echo "target=$TARGET"
  echo "lineage=$LINEAGE"
  printf 'repo_head='
  git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown
} > "$EVIDENCE_DIR/install-metadata.txt"
stat -Lc 'source=%n owner=%U:%G mode=%a bytes=%s' "$SOURCE" > "$EVIDENCE_DIR/source-metadata.txt" 2>/dev/null || true

sh -n "$SOURCE" || fail "reviewed renewal hook source has invalid shell syntax"
install -o root -g root -m 0755 "$SOURCE" "$TARGET"
sh -n "$TARGET" || { rm -f "$TARGET"; fail "installed renewal hook failed shell syntax validation"; }

# Certbot directory hooks run for all lineages. Confirm unrelated lineages are a
# clean no-op before accepting the installation.
RENEWED_LINEAGE=/etc/letsencrypt/live/not-ntp.ww.cx \
RENEWED_DOMAINS=not-ntp.ww.cx \
  "$TARGET" || { rm -f "$TARGET"; fail "installed renewal hook did not ignore an unrelated lineage"; }

stat -Lc 'installed=%n owner=%U:%G mode=%a bytes=%s' "$TARGET" > "$EVIDENCE_DIR/installed-metadata.txt"

printf '%s\n' \
  "WW.CX Certbot deploy hook installed for the ntp.ww.cx lineage." \
  "Hook: $TARGET" \
  "The hook was NOT executed against the live ntp.ww.cx lineage by this installer." \
  "A controlled renewal/deploy-hook validation remains required." \
  "Evidence: $EVIDENCE_DIR"
