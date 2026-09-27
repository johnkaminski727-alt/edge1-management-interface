#!/usr/bin/env bash
# Assignment 247: two-run isolation regression, NON-PRODUCTION ONLY.
# Only nft changes occur AFTER unshare --net verifies a distinct namespace.
# Do NOT substitute host sudo nft when namespace isolation is unavailable.
set -euo pipefail
umask 077

ORIGINAL_NETNS="$(readlink /proc/self/ns/net)"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
A="bigbird_spamhaus_run_0123456789abcdef0123456789abcdef"
B="bigbird_spamhaus_run_abcdef0123456789abcdef0123456789"
cat > "$ROOT/a.nft" <<'NFT'
create table inet bigbird_spamhaus_run_0123456789abcdef0123456789abcdef {
    comment "edge1-spamhaus-run:0123456789abcdef0123456789abcdef";
}
table inet bigbird_spamhaus_run_0123456789abcdef0123456789abcdef {
    set drop4 { type ipv4_addr; flags interval; elements = { 192.0.2.0/24 }; }
    chain input {
        type filter hook input priority -110; policy accept;
        ip saddr @drop4 counter drop
    }
}
NFT
cat > "$ROOT/b.nft" <<'NFT'
create table inet bigbird_spamhaus_run_abcdef0123456789abcdef0123456789 {
    comment "edge1-spamhaus-run:abcdef0123456789abcdef0123456789";
}
table inet bigbird_spamhaus_run_abcdef0123456789abcdef0123456789 {
    set drop4 { type ipv4_addr; flags interval; elements = { 198.51.100.0/24 }; }
    chain input {
        type filter hook input priority -110; policy accept;
        ip saddr @drop4 counter drop
    }
}
NFT

cat > "$ROOT/inner.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
actual="$(readlink /proc/self/ns/net)"
if [[ "$actual" == "$A247_ORIGINAL_NETNS" ]]; then
    echo "STOP: not isolated; refusing all nft mutations"
    exit 2
fi
echo "PASS: distinct network namespace verified"

name_a="bigbird_spamhaus_run_0123456789abcdef0123456789abcdef"
name_b="bigbird_spamhaus_run_abcdef0123456789abcdef0123456789"
nft --check --file "$A247_ROOT/a.nft"
nft --check --file "$A247_ROOT/b.nft"
nft --file "$A247_ROOT/a.nft"
nft --file "$A247_ROOT/b.nft"

verify_owner() {
    local name="$1" rid="$2"
    nft -j list table inet "$name" | python3 -c '
import json, sys
data=json.load(sys.stdin)
target=sys.argv[1]; expected="edge1-spamhaus-run:"+sys.argv[2]
records=[r["table"] for r in data["nftables"] if "table" in r
         and r["table"].get("family")=="inet" and r["table"].get("name")==target]
if len(records)!=1 or records[0].get("comment")!=expected:
    raise SystemExit("FAIL: incorrect ownership marker")
' "$name" "$rid"
}
verify_owner "$name_a" "0123456789abcdef0123456789abcdef"
verify_owner "$name_b" "abcdef0123456789abcdef0123456789"
echo "PASS: both tagged run tables coexist independently"

if nft --file "$A247_ROOT/a.nft" >/dev/null 2>&1; then
    echo "FAIL: duplicate run A creation succeeded"
    exit 3
fi
echo "PASS: duplicate run creation refused"

nft delete table inet "$name_a"
if nft list table inet "$name_a" >/dev/null 2>&1; then
    echo "FAIL: run A still present after scoped delete"
    exit 4
fi
verify_owner "$name_b" "abcdef0123456789abcdef0123456789"
echo "PASS: deleting A did not remove or alter B"

nft delete table inet "$name_b"
echo "PASS: isolated run A and run B cleaned up"
SH

echo "=== Assignment 247 isolated dual-run nft rehearsal ==="
sudo env A247_ORIGINAL_NETNS="$ORIGINAL_NETNS" A247_ROOT="$ROOT" \
    unshare --net -- /bin/bash "$ROOT/inner.sh"

echo "=== Original namespace: READ ONLY production check ==="
if sudo nft list table inet bigbird_spamhaus >/dev/null; then
    echo "PASS: original production Spamhaus table still present"
else
    echo "ALERT: production table missing or unreadable"
    exit 5
fi
echo "=== Assignment 247 complete ==="
