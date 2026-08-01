#!/bin/sh
set -eu
umask 077

EXPECTED_HOST="edge1.ww.cx"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --expected-host)
            [ "$#" -ge 2 ] || { echo "ERROR missing hostname" >&2; exit 2; }
            EXPECTED_HOST=$2
            shift 2
            ;;
        -h|--help)
            echo "Usage: sudo $0 [--expected-host HOST]"
            echo "Read-only inventory of listening sockets, interface scope, service ownership, Asterisk surfaces, and firewall policy."
            exit 0
            ;;
        *)
            echo "ERROR unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR run with sudo" >&2; exit 2; }
HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || {
    echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2
    exit 2
}

for command in date hostname id ip ss awk grep sed sort systemctl nft asterisk; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing command: $command" >&2
        exit 2
    }
done

warnings=0
failures=0

warn() {
    warnings=$((warnings + 1))
    echo "WARNING: $*"
}

fail() {
    failures=$((failures + 1))
    echo "FAIL: $*"
}

section() {
    echo
    echo "=== $* ==="
}

safe_cli() {
    command_text=$1
    asterisk -rx "$command_text" 2>&1 || true
}

echo "WW.CX EDGE1 COMPREHENSIVE LISTENER EXPOSURE AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; local observation only; no configuration, service, listener, route, certificate, firewall, package, call, container, or traffic change"
echo "Boundary: this is not an external Internet scan and does not by itself prove upstream-provider reachability"

section "HOST INTERFACES AND ROUTES"
ip -brief address show 2>&1 | sed -E 's/[[:space:]]+/ /g'
echo
ip route show table all 2>&1 | sed -n '1,200p'
if command -v sysctl >/dev/null 2>&1; then
    sysctl net.ipv6.bindv6only net.ipv4.ip_forward net.ipv6.conf.all.forwarding 2>/dev/null || true
fi

PUBLIC_V4=$(ip -o -4 address show scope global 2>/dev/null |
    awk '$2 != "lo" && $2 !~ /^wg/ {split($4, value, "/"); print value[1]}' |
    sort -u)
PUBLIC_V6=$(ip -o -6 address show scope global 2>/dev/null |
    awk '$2 != "lo" && $2 !~ /^wg/ {split($4, value, "/"); print value[1]}' |
    sort -u)
WG_V4=$(ip -o -4 address show 2>/dev/null |
    awk '$2 ~ /^wg/ {split($4, value, "/"); print value[1]}' |
    sort -u)
WG_V6=$(ip -o -6 address show 2>/dev/null |
    awk '$2 ~ /^wg/ {split($4, value, "/"); print value[1]}' |
    sort -u)

echo "public_or_non_vpn_ipv4=${PUBLIC_V4:-none}"
echo "public_or_non_vpn_ipv6=${PUBLIC_V6:-none}"
echo "wireguard_ipv4=${WG_V4:-none}"
echo "wireguard_ipv6=${WG_V6:-none}"

section "ALL LISTENING SOCKETS"
SOCKETS=$(ss -H -lntup 2>&1 || true)
if [ -z "$SOCKETS" ]; then
    fail "No listener inventory was returned by ss"
else
    printf '%s\n' "$SOCKETS" | sort
fi

section "WILDCARD-BOUND LISTENERS"
WILDCARD=$(printf '%s\n' "$SOCKETS" |
    grep -E '(^|[[:space:]])(0\.0\.0\.0|\*|\[::\]):[0-9]+' || true)
if [ -n "$WILDCARD" ]; then
    printf '%s\n' "$WILDCARD" | sort
    warn "One or more listeners are bound to wildcard addresses; firewall scope must be evaluated for each"
else
    echo "No wildcard-bound listeners found."
fi

section "DIRECT NON-VPN ADDRESS LISTENERS"
DIRECT=""
for address in $PUBLIC_V4 $PUBLIC_V6; do
    current=$(printf '%s\n' "$SOCKETS" | grep -F "$address:" || true)
    if [ -n "$current" ]; then
        DIRECT="${DIRECT}${DIRECT:+
}${current}"
    fi
done
if [ -n "$DIRECT" ]; then
    printf '%s\n' "$DIRECT" | sort -u
    warn "One or more processes listen directly on a non-loopback, non-WireGuard address"
else
    echo "No listener was matched directly to a non-loopback, non-WireGuard address."
fi

section "WIREGUARD-ADDRESS LISTENERS"
WG_LISTENERS=""
for address in $WG_V4 $WG_V6; do
    current=$(printf '%s\n' "$SOCKETS" | grep -F "$address:" || true)
    if [ -n "$current" ]; then
        WG_LISTENERS="${WG_LISTENERS}${WG_LISTENERS:+
}${current}"
    fi
done
if [ -n "$WG_LISTENERS" ]; then
    printf '%s\n' "$WG_LISTENERS" | sort -u
else
    echo "No listener was matched directly to a WireGuard interface address."
fi

section "LOOPBACK-ONLY LISTENERS"
printf '%s\n' "$SOCKETS" |
    grep -E '(^|[[:space:]])(127\.[0-9.]+|\[::1\]):[0-9]+' |
    sort || true

section "SYSTEMD SOCKET ACTIVATION"
systemctl list-sockets --all --no-pager --no-legend 2>&1 | sed -n '1,300p' || true

section "ENABLED SERVICE INVENTORY"
systemctl list-unit-files --state=enabled --type=service --no-pager --no-legend 2>&1 |
    sed -n '1,400p' || true

section "ASTERISK CORE AND INTERFACE SURFACES"
safe_cli 'core show version'
safe_cli 'core show channels count'
echo
safe_cli 'http show status'
echo
safe_cli 'manager show settings'
echo
safe_cli 'ari show status'
echo
safe_cli 'rtp show settings'
echo
safe_cli 'pjsip show transports'
echo
safe_cli 'module show like res_http_websocket'
safe_cli 'module show like res_ari'
safe_cli 'module show like chan_websocket'
safe_cli 'module show like res_pjsip_transport_websocket'

section "ASTERISK-OWNED SOCKETS"
ASTERISK_SOCKETS=$(printf '%s\n' "$SOCKETS" | grep -F '"asterisk"' || true)
printf '%s\n' "$ASTERISK_SOCKETS" | sort
ASTERISK_HIGH_UDP=$(printf '%s\n' "$ASTERISK_SOCKETS" |
    awk '$1 == "udp" {
        local=$5
        sub(/^.*:/, "", local)
        if (local ~ /^[0-9]+$/ && local > 1024 && local != 5061) print
    }' || true)
if [ -n "$ASTERISK_HIGH_UDP" ]; then
    echo "Asterisk-owned high UDP sockets requiring feature/range attribution:"
    printf '%s\n' "$ASTERISK_HIGH_UDP" | sort
    warn "Asterisk owns high UDP sockets outside the known loopback SIP transport"
fi

section "APACHE EFFECTIVE LISTENERS AND VHOSTS"
if command -v apache2ctl >/dev/null 2>&1; then
    apache2ctl -t -D DUMP_RUN_CFG 2>&1 | sed -n '1,300p' || true
    apache2ctl -S 2>&1 | sed -n '1,300p' || true
else
    echo "apache2ctl not installed"
fi

section "CONTAINER-PUBLISHED PORTS"
if command -v docker >/dev/null 2>&1; then
    docker ps --format '{{.Names}}\t{{.Ports}}' 2>&1 | sed -n '1,200p' || true
else
    echo "docker not installed"
fi
if command -v podman >/dev/null 2>&1; then
    podman ps --format '{{.Names}}\t{{.Ports}}' 2>&1 | sed -n '1,200p' || true
else
    echo "podman not installed"
fi

section "AUTHORITATIVE NFTABLES INPUT PATH"
NFT_INPUT=$(nft -a list chain inet wwcxfw input 2>&1 || true)
if [ -n "$NFT_INPUT" ]; then
    printf '%s\n' "$NFT_INPUT"
else
    fail "Authoritative inet wwcxfw input chain was not available"
fi

if printf '%s\n' "$NFT_INPUT" | grep -Fq 'iifname "wg0" accept'; then
    warn "The current policy broadly accepts every service reached through wg0"
fi

section "OTHER INPUT BASE CHAINS"
nft -a list ruleset 2>/dev/null |
    awk '
        /^[[:space:]]*table / {table=$0}
        /^[[:space:]]*chain / {chain=$0; capture=0}
        /hook input/ {print table; print chain; print; capture=1; next}
        capture && /policy (accept|drop|reject)/ {print}
    ' || true

section "PUBLIC FIREWALL ALLOW EXPRESSIONS"
printf '%s\n' "$NFT_INPUT" |
    grep -E 'dport|iifname|ip saddr|ip6 saddr|accept|drop|reject|policy' || true

echo
if printf '%s\n' "$NFT_INPUT" | grep -Eq 'tcp dport \{[[:space:]]*80,[[:space:]]*443[[:space:]]*\} accept'; then
    echo "Observed explicit public web allow-list includes TCP 80 and 443."
fi

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi

echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No configuration, service, listener, route, certificate, firewall, package, call, container, or traffic change was performed."
