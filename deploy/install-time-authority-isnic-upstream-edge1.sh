#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$ROOT/modules/time-authority/config/wwcx-isnic-upstream.conf"
TARGET="/etc/chrony/conf.d/wwcx-isnic-upstream.conf"
APPROVAL=${WWCX_TIME_APPROVE_ISNIC_UPSTREAM:-}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="/var/lib/wwcx-deployment-evidence/public-ntp-server/isnic-upstream-$STAMP"
PROBE_CFG=$(mktemp)
PROBE_OUT=$(mktemp)
BACKUP_PRESENT=0
APPLIED=0

cleanup_tmp() {
    rm -f "$PROBE_CFG" "$PROBE_OUT"
}

rollback() {
    rc=$?
    trap - EXIT HUP INT TERM

    if [ "$APPLIED" -eq 1 ]; then
        echo "ROLLBACK: restoring previous ISNIC fragment state" >&2
        if [ "$BACKUP_PRESENT" -eq 1 ]; then
            cp "$EVIDENCE_DIR/wwcx-isnic-upstream.conf.before" "$TARGET"
            chown root:root "$TARGET"
            chmod 0644 "$TARGET"
        else
            rm -f "$TARGET"
        fi
        systemctl restart chrony.service >/dev/null 2>&1 || true
        chronyc waitsync 20 0.05 >/dev/null 2>&1 || true
    fi

    cleanup_tmp
    exit "$rc"
}

trap rollback EXIT HUP INT TERM

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root"
[ "$APPROVAL" = "YES" ] || fail "set WWCX_TIME_APPROVE_ISNIC_UPSTREAM=YES after explicit production approval"
[ -r "$SOURCE" ] || fail "missing reviewed source fragment: $SOURCE"

grep -Fxq 'server ht-time01.isnic.is iburst' "$SOURCE" || fail "reviewed fragment does not contain the expected ISNIC source"
! grep -Eq '(^|[[:space:]])prefer([[:space:]]|$)' "$SOURCE" || fail "ISNIC source must not be forced with prefer"

for command in python3 systemctl chronyc getent ss openssl install mkdir cp rm chown chmod; do
    command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done

systemctl is-active --quiet chrony.service || fail "chrony.service is not active before change"
getent ahostsv4 ht-time01.isnic.is >/dev/null 2>&1 || fail "cannot resolve ht-time01.isnic.is"

cat >"$PROBE_CFG" <<'JSON'
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "isnic-preflight",
      "server_name": "ht-time01.isnic.is",
      "provider": "ISNIC",
      "expected_stratum": 1
    }
  ]
}
JSON

python3 "$ROOT/tools/time_authority/ntp_rtt_probe.py" \
    --observer-id edge1-isnic-production-preflight \
    --sources "$PROBE_CFG" \
    --output "$PROBE_OUT" \
    --timeout 1.5 >/dev/null || fail "direct ISNIC NTP preflight failed"

python3 - "$PROBE_OUT" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    records = [json.loads(line) for line in handle if line.strip()]

if not records:
    raise SystemExit("no probe record")
r = records[-1]
if not r.get("reachable"):
    raise SystemExit("candidate unreachable")
if r.get("stratum") != 1:
    raise SystemExit(f"unexpected stratum: {r.get('stratum')}")
if r.get("leap_indicator") == 3:
    raise SystemExit("candidate reports unsynchronized leap state")
print(
    "PASS: live ISNIC preflight",
    f"address={r.get('resolved_address')}",
    f"stratum={r.get('stratum')}",
    f"rtt_ms={r.get('rtt_ms')}",
    f"offset_ms={r.get('clock_offset_ms')}",
    f"dispersion_ms={r.get('root_dispersion_ms')}",
)
PY

mkdir -p "$EVIDENCE_DIR"
chmod 0750 "$EVIDENCE_DIR"
chronyc tracking >"$EVIDENCE_DIR/chronyc-tracking.before.txt" 2>&1 || true
chronyc -N sources -v >"$EVIDENCE_DIR/chronyc-sources.before.txt" 2>&1 || true
chronyc -N sourcestats -v >"$EVIDENCE_DIR/chronyc-sourcestats.before.txt" 2>&1 || true
ss -H -lunp 'sport = :123' >"$EVIDENCE_DIR/udp123.before.txt" 2>&1 || true
ss -H -ltnp 'sport = :4460' >"$EVIDENCE_DIR/tcp4460.before.txt" 2>&1 || true
cp "$PROBE_OUT" "$EVIDENCE_DIR/isnic-preflight.jsonl"
cp "$SOURCE" "$EVIDENCE_DIR/wwcx-isnic-upstream.conf.reviewed"

if [ -e "$TARGET" ]; then
    BACKUP_PRESENT=1
    cp "$TARGET" "$EVIDENCE_DIR/wwcx-isnic-upstream.conf.before"
fi

install -o root -g root -m 0644 "$SOURCE" "$TARGET"
APPLIED=1

systemctl restart chrony.service
systemctl is-active --quiet chrony.service || fail "chrony.service did not return active"
chronyc waitsync 30 0.05 >/dev/null || fail "chronyd did not reach synchronized state"

chronyc -N sources -v >"$EVIDENCE_DIR/chronyc-sources.after.txt"
chronyc -N sourcestats -v >"$EVIDENCE_DIR/chronyc-sourcestats.after.txt"
chronyc tracking >"$EVIDENCE_DIR/chronyc-tracking.after.txt"

grep -Fq 'ht-time01.isnic.is' "$EVIDENCE_DIR/chronyc-sources.after.txt" || fail "ISNIC source is not present after restart"
grep -Fq 'Leap status     : Normal' "$EVIDENCE_DIR/chronyc-tracking.after.txt" || fail "chrony leap status is not Normal"

ss -H -lunp 'sport = :123' >"$EVIDENCE_DIR/udp123.after.txt"
grep -q . "$EVIDENCE_DIR/udp123.after.txt" || fail "UDP/123 listener missing after restart"

ss -H -ltnp 'sport = :4460' >"$EVIDENCE_DIR/tcp4460.after.txt"
grep -q . "$EVIDENCE_DIR/tcp4460.after.txt" || fail "TCP/4460 NTS-KE listener missing after restart"

sh "$ROOT/deploy/time-authority-ntp-server-edge1-smoke-test.sh" >"$EVIDENCE_DIR/public-ntp-smoke.after.txt" 2>&1 || fail "local public NTP smoke test failed"

if ! timeout 8 openssl s_client \
    -connect 127.0.0.1:4460 \
    -servername ntp.ww.cx \
    -alpn ntske/1 </dev/null >"$EVIDENCE_DIR/nts-local-tls.after.txt" 2>&1; then
    fail "local NTS TLS handshake failed"
fi
grep -Fq 'ALPN protocol: ntske/1' "$EVIDENCE_DIR/nts-local-tls.after.txt" || fail "NTS ALPN ntske/1 was not negotiated"

APPLIED=0
cleanup_tmp
trap - EXIT HUP INT TERM

echo "PASS: ISNIC GNSS-backed upstream installed"
echo "Source:   ht-time01.isnic.is"
echo "Fragment: $TARGET"
echo "Evidence: $EVIDENCE_DIR"
echo "No DNS or firewall change was made."
