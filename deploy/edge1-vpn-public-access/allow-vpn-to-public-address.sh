#!/bin/sh
# Let WireGuard (wg0) clients reach Edge1's own public address on TCP 443 and 22.
#
# Why: a full-tunnel VPN client's traffic to Edge1's public IPv4 arrives on wg0,
# but UFW only accepts that address on the internet interface (ens3), so
# https://mcp-b159.ww.cx (and `ssh edge1`) time out while the VPN is up.
#
# Scope: source 10.77.0.0/24, interface wg0, destination = the ens3 IPv4,
# ports 443 and 22 only. Nothing new is opened to the internet.
#
#   sudo sh allow-vpn-to-public-address.sh            # dry run (default)
#   sudo sh allow-vpn-to-public-address.sh --apply
#   sudo sh allow-vpn-to-public-address.sh --remove
set -eu

WAN_IF=${WWCX_WAN_IF:-ens3}
VPN_IF=${WWCX_VPN_IF:-wg0}
VPN_NET=${WWCX_VPN_NET:-10.77.0.0/24}
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/vpn-public-access
PORTS="443 22"
COMMENT_PREFIX=wwcx:vpn-public

MODE=dry-run
case "${1:-}" in
    "") ;;
    --apply) MODE=apply ;;
    --remove) MODE=remove ;;
    *) echo "usage: $0 [--apply|--remove]" >&2; exit 2 ;;
esac

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok:   $*"; }

[ "$(id -u)" -eq 0 ] || fail "run with sudo"
for cmd in ufw ip awk grep; do command -v "$cmd" >/dev/null 2>&1 || fail "missing command: $cmd"; done

ufw status | grep -q '^Status: active' || fail "UFW is not active; refusing to change an unmanaged firewall"
ip link show "$VPN_IF" >/dev/null 2>&1 || fail "VPN interface $VPN_IF not found"
PUBLIC_IP=$(ip -4 -o addr show dev "$WAN_IF" scope global | awk '{print $4}' | cut -d/ -f1 | head -n 1)
[ -n "$PUBLIC_IP" ] || fail "no global IPv4 on $WAN_IF"
ok "UFW active; $VPN_IF present; public address on $WAN_IF is $PUBLIC_IP"

rule_args() { # $1 = port
    echo "in on $VPN_IF proto tcp from $VPN_NET to $PUBLIC_IP port $1"
}
comment_for() { # $1 = port
    case "$1" in 443) echo "$COMMENT_PREFIX-https" ;; 22) echo "$COMMENT_PREFIX-ssh" ;; esac
}
present() { # $1 = port
    ufw status | grep -F "$(comment_for "$1")" | grep -q "$PUBLIC_IP $1/tcp"
}

for port in $PORTS; do
    if present "$port"; then ok "port $port: rule already present"; else echo "plan: ufw allow $(rule_args "$port") comment '$(comment_for "$port")'"; fi
done

if [ "$MODE" = dry-run ]; then
    echo
    echo "Dry run complete. Nothing was changed."
    echo "Apply with: sudo sh $0 --apply"
    exit 0
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$EVIDENCE_ROOT/$MODE-$STAMP"
install -d -m 0750 "$EVIDENCE"
ufw status numbered > "$EVIDENCE/ufw-status.before.txt"

if [ "$MODE" = remove ]; then
    for port in $PORTS; do
        if present "$port"; then
            # shellcheck disable=SC2046
            ufw delete allow $(rule_args "$port") >/dev/null
            ok "port $port: rule removed"
        fi
    done
else
    ADDED=
    for port in $PORTS; do
        present "$port" && continue
        # shellcheck disable=SC2046
        if ! ufw allow $(rule_args "$port") comment "$(comment_for "$port")" >/dev/null; then
            for p in $ADDED; do ufw delete allow $(rule_args "$p") >/dev/null || true; done
            fail "ufw rejected the port $port rule; rules added in this run were removed"
        fi
        ADDED="$ADDED $port"
        present "$port" || fail "port $port rule not visible after adding"
        ok "port $port: rule added"
    done
fi

ufw status numbered > "$EVIDENCE/ufw-status.after.txt"
echo
ufw status | grep -F "$COMMENT_PREFIX" || echo "(no $COMMENT_PREFIX rules present)"
echo "Evidence: $EVIDENCE"
