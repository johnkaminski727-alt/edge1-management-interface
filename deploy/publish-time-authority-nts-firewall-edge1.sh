#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PUBLIC_IP=${WWCX_NTP_PUBLIC_IPV4:-89.147.109.253}
PERSIST=${WWCX_NTP_NFTABLES_CONF:-/etc/nftables.conf}
EVIDENCE_ROOT=${WWCX_NTP_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/public-ntp-server}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/nts-firewall-$STAMP"
RULE_COMMENT=wwcx:public-nts-ke-v4
LIVE_RULE_TEXT="ip daddr $PUBLIC_IP tcp dport 4460 accept"
PERSIST_CHANGED=0
LIVE_INSERTED=0

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

live_rule_present() {
  nft -a list chain inet wwcxfw input 2>/dev/null | \
    grep -F "$LIVE_RULE_TEXT" | grep -Fq "$RULE_COMMENT"
}

rollback_current_changes() {
  if [ "$PERSIST_CHANGED" -eq 1 ] && [ -f "$EVIDENCE_DIR/nftables.conf.before" ]; then
    cp -a "$EVIDENCE_DIR/nftables.conf.before" "$PERSIST" || true
  fi
  if [ "$LIVE_INSERTED" -eq 1 ]; then
    HANDLE=$(nft -a list chain inet wwcxfw input 2>/dev/null | \
      grep -F "$LIVE_RULE_TEXT" | grep -F "$RULE_COMMENT" | \
      awk '{for (i=1; i<=NF; i++) if ($i == "handle") {print $(i+1); exit}}')
    [ -n "${HANDLE:-}" ] && nft delete rule inet wwcxfw input handle "$HANDLE" || true
  fi
}

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root"
[ "${WWCX_NTS_APPROVE_PUBLIC_TCP4460:-}" = "YES" ] || \
  fail "set WWCX_NTS_APPROVE_PUBLIC_TCP4460=YES only after explicit approval to expose NTS-KE on public TCP/4460"

for cmd in nft python3 systemctl ss getent grep awk cp install; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done

[ -r "$PERSIST" ] || fail "persistent nftables file is not readable: $PERSIST"
systemctl is-active --quiet chrony.service || fail "chrony.service is not active"

LISTENER=$(ss -H -ltnp 'sport = :4460' 2>/dev/null || true)
[ -n "$LISTENER" ] || fail "chronyd is not listening on TCP/4460"
printf '%s\n' "$LISTENER" | grep -q 'chronyd' || fail "TCP/4460 is not owned by chronyd"

if ! getent ahostsv4 ntp.ww.cx | awk '{print $1}' | grep -Fxq "$PUBLIC_IP"; then
  fail "ntp.ww.cx does not resolve locally to expected IPv4 $PUBLIC_IP"
fi

if ! grep -Fq 'table inet wwcxfw {' "$PERSIST"; then
  fail "persistent nftables file does not define table inet wwcxfw"
fi
if ! grep -Fq 'tcp dport { 80, 443 } accept comment "wwcx:public-web"' "$PERSIST"; then
  fail "persistent nftables file does not contain expected public-web anchor"
fi

sh "$ROOT/deploy/time-authority-nts-edge1-smoke-test.sh"

install -d -m 0750 "$EVIDENCE_DIR"
cp -a "$PERSIST" "$EVIDENCE_DIR/nftables.conf.before"
nft -a list ruleset > "$EVIDENCE_DIR/live-ruleset.before.nft"
(ss -H -ltnp 'sport = :4460' 2>&1 || true) > "$EVIDENCE_DIR/tcp4460.before.txt"
(getent ahostsv4 ntp.ww.cx 2>&1 || true) > "$EVIDENCE_DIR/ntp-dns.before.txt"

if ! grep -Fq "ip daddr $PUBLIC_IP tcp dport 4460 accept comment \"$RULE_COMMENT\"" "$PERSIST"; then
  if grep -Fq "$RULE_COMMENT" "$PERSIST"; then
    fail "persistent file contains $RULE_COMMENT but not the reviewed IPv4 rule; manual review required"
  fi
  python3 - "$PERSIST" "$PUBLIC_IP" <<'PY'
import os
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
public_ip = sys.argv[2]
text = path.read_text(encoding="utf-8")
anchor = '        tcp dport { 80, 443 } accept comment "wwcx:public-web"\n'
if anchor not in text:
    raise SystemExit("persistent public-web anchor not found")
rule = '        ip daddr {} tcp dport 4460 accept comment "wwcx:public-nts-ke-v4"\n'.format(public_ip)
text = text.replace(anchor, rule + anchor, 1)
st = path.stat()
tmp = path.with_name(path.name + ".wwcx-nts.tmp")
tmp.write_text(text, encoding="utf-8")
os.chmod(str(tmp), st.st_mode)
os.chown(str(tmp), st.st_uid, st.st_gid)
os.replace(str(tmp), str(path))
PY
  PERSIST_CHANGED=1
fi

if ! nft -c -f "$PERSIST"; then
  rollback_current_changes
  fail "persistent nftables syntax check failed; current-run changes rolled back"
fi

if ! live_rule_present; then
  if nft -a list chain inet wwcxfw input | grep -Fq "$RULE_COMMENT"; then
    rollback_current_changes
    fail "live chain contains $RULE_COMMENT but not the reviewed IPv4 rule; manual review required"
  fi

  WEB_HANDLE=$(nft -a list chain inet wwcxfw input | awk '/wwcx:public-web/ {for (i=1; i<=NF; i++) if ($i == "handle") {print $(i+1); exit}}')
  if [ -z "$WEB_HANDLE" ]; then
    rollback_current_changes
    fail "could not locate live public-web rule handle; current-run changes rolled back"
  fi

  LIVE_BATCH="$EVIDENCE_DIR/live-insert.nft"
  printf 'insert rule inet wwcxfw input position %s ip daddr %s tcp dport 4460 accept comment "%s"\n' \
    "$WEB_HANDLE" "$PUBLIC_IP" "$RULE_COMMENT" > "$LIVE_BATCH"

  if ! nft -c -f "$LIVE_BATCH"; then
    rollback_current_changes
    fail "live NTS firewall insertion syntax check failed; current-run changes rolled back"
  fi
  if ! nft -f "$LIVE_BATCH"; then
    rollback_current_changes
    fail "live NTS firewall insertion failed; current-run changes rolled back"
  fi
  LIVE_INSERTED=1
fi

if ! live_rule_present; then
  rollback_current_changes
  fail "live NTS firewall rule verification failed; current-run changes rolled back"
fi
if ! grep -Fq "ip daddr $PUBLIC_IP tcp dport 4460 accept comment \"$RULE_COMMENT\"" "$PERSIST"; then
  rollback_current_changes
  fail "persistent NTS firewall rule verification failed; current-run changes rolled back"
fi

# Do not reload /etc/nftables.conf. Runtime Big Bird blocklist/logging controls
# are not fully represented in the boot-time base file.
if ! sh "$ROOT/deploy/time-authority-nts-edge1-smoke-test.sh"; then
  rollback_current_changes
  fail "post-firewall local NTS smoke test failed; current-run changes rolled back"
fi

cp -a "$PERSIST" "$EVIDENCE_DIR/nftables.conf.after"
nft -a list ruleset > "$EVIDENCE_DIR/live-ruleset.after.nft"
(nft -a list chain inet wwcxfw input 2>&1 || true) > "$EVIDENCE_DIR/wwcxfw-input.after.txt"
(ss -H -ltnp 'sport = :4460' 2>&1 || true) > "$EVIDENCE_DIR/tcp4460.after.txt"

printf '%s\n' \
  "WW.CX public IPv4 NTS-KE firewall publication installed." \
  "Public NTS-KE service: ntp.ww.cx -> $PUBLIC_IP TCP/4460" \
  "IPv6 NTS firewall publication: not changed" \
  "nftables.service reload: intentionally not performed" \
  "Rollback evidence: $EVIDENCE_DIR" \
  "Next acceptance step: verify NTS-KE and an authenticated NTS time exchange from outside Edge1."
