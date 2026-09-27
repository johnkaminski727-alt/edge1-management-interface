#!/usr/bin/env bash
# Assignment 246 — OPTIONAL operator-run rehearsal, NOT a production installer.
# Tests nftables create-only + table comment in a NEW network namespace.
# Must be invoked as wwadmin on Edge1 with sudo capability; no reboot or timer.
set -euo pipefail
umask 077

host_netns="$(readlink /proc/self/ns/net)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

cat > "$work/owned.nft" <<'NFT'
create table inet edge1_a246_probe {
    comment "edge1-a246-run:0123456789abcdef0123456789abcdef";
}

table inet edge1_a246_probe {
    set probe4 {
        type ipv4_addr
        flags interval
        elements = { 198.51.100.0/24 }
    }
    chain input {
        type filter hook input priority -110; policy accept;
        ip saddr @probe4 counter drop
    }
}
NFT

echo "=== Assignment 246: isolated netns ownership rehearsal ==="
echo "Production nftables tables will not be modified."

# An entirely new network namespace gets a separate nftables ruleset.
# Stop BEFORE any nft write if isolation did not take effect.
sudo env A246_HOST_NETNS="$host_netns" A246_TEST_FILE="$work/owned.nft" \
    unshare --net -- bash -ceu '
    current="$(readlink /proc/self/ns/net)"
    if [[ "$current" == "$A246_HOST_NETNS" ]]; then
        echo "STOP: network namespace not isolated"
        exit 2
    fi
    echo "PASS: network namespace isolation confirmed"
    nft --check --file "$A246_TEST_FILE"
    nft --file "$A246_TEST_FILE"
    nft -j list table inet edge1_a246_probe | python3 -c '\''import json,sys
data=json.load(sys.stdin)
table=[x["table"] for x in data["nftables"] if "table" in x]
assert len(table)==1, "Expected exactly one isolated test table"
actual=table[0].get("comment")
expected="edge1-a246-run:0123456789abcdef0123456789abcdef"
if actual!=expected:
    print("FAIL: owner comment missing or mismatched; present:",repr(actual))
    raise SystemExit(3)
print("PASS: create-only transaction and table comment verified")
'\''
    if nft --file "$A246_TEST_FILE" >/dev/null 2>&1; then
        echo "FAIL: duplicate create unexpectedly succeeded"
        exit 3
    fi
    echo "PASS: duplicate create refused"
    nft delete table inet edge1_a246_probe
    echo "PASS: isolated test table deleted"
'

# Read-only check in the original (production) namespace.
if sudo nft list table inet bigbird_spamhaus >/dev/null 2>&1; then
    echo "PASS: production Spamhaus table still present"
else
    echo "WARNING: unable to verify production table; investigate immediately"
    exit 4
fi
echo "=== Assignment 246 complete ==="
