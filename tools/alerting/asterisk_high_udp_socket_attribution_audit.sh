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
            echo "Read-only attribution audit for Asterisk-owned high UDP sockets."
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR run with sudo" >&2; exit 2; }
HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || { echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2; exit 2; }

for command in asterisk awk grep sed sort ss systemctl readlink date hostname id ps find stat sha256sum; do
    command -v "$command" >/dev/null 2>&1 || { echo "ERROR missing command: $command" >&2; exit 2; }
done

warnings=0
failures=0
warn() { warnings=$((warnings + 1)); echo "WARNING: $*"; }
fail() { failures=$((failures + 1)); echo "FAIL: $*"; }
section() { echo; echo "=== $* ==="; }

safe_config_lines() {
    file=$1
    [ -f "$file" ] || return 0
    awk '
        /^[[:space:]]*[#;]/ {next}
        /^[[:space:]]*$/ {next}
        /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {print FILENAME ":" FNR ":" $0; next}
        /^[[:space:]]*(rtpstart|rtpend|strictrtp|probation|icesupport|stunaddr|turnaddr|bindaddr|bindport|external_media_address|external_signaling_address|local_net|media_address|use_avpf|media_encryption|webrtc|protocol)[[:space:]]*=/ {
            line=$0
            sub(/^[[:space:]]*/, "", line)
            if (line ~ /^(turnaddr|stunaddr)=/) {
                sub(/=.*/, "=[configured]", line)
            }
            print FILENAME ":" FNR ":" line
        }
    ' "$file"
}

echo "WW.CX ASTERISK HIGH UDP SOCKET ATTRIBUTION AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no tracer attachment, packet capture, configuration, service, listener, route, certificate, firewall, package, call, or traffic change"

section "CORE STATE"
asterisk -rx 'core show version' 2>&1 || true
asterisk -rx 'core show uptime' 2>&1 || true
asterisk -rx 'core show channels count' 2>&1 || true
echo "service_active=$(systemctl is-active asterisk 2>&1 || true)"
PID=$(systemctl show -p MainPID --value asterisk 2>/dev/null || true)
case "$PID" in
    ''|0|*[!0-9]*) fail "Unable to resolve Asterisk MainPID"; PID="" ;;
    *) echo "asterisk_pid=$PID"; ps -p "$PID" -o pid=,lstart=,etime=,args= 2>/dev/null || true ;;
esac

section "ASTERISK UDP SOCKETS"
if [ -n "$PID" ]; then
    UDP_LINES=$(ss -H -lunpe 2>&1 | grep "pid=$PID" || true)
    printf '%s\n' "$UDP_LINES"
    HIGH_PORTS=$(printf '%s\n' "$UDP_LINES" |
        sed -n "s/.*:\([0-9][0-9]*\)[[:space:]].*pid=$PID.*/\1/p" |
        awk '$1 > 1024 && $1 != 5061 {print $1}' |
        sort -n -u)
    if [ -n "$HIGH_PORTS" ]; then
        echo "high_udp_ports=$(printf '%s' "$HIGH_PORTS" | tr '\n' ',' | sed 's/,$//')"
    else
        warn "No high Asterisk-owned UDP sockets were found"
    fi
else
    UDP_LINES=""
    HIGH_PORTS=""
fi

section "SOCKET FILE DESCRIPTORS AND INODES"
if [ -n "$PID" ] && [ -d "/proc/$PID/fd" ]; then
    for fdpath in /proc/"$PID"/fd/*; do
        [ -e "$fdpath" ] || continue
        target=$(readlink "$fdpath" 2>/dev/null || true)
        case "$target" in
            socket:\[*\])
                fd=${fdpath##*/}
                inode=$(printf '%s\n' "$target" | sed -n 's/^socket:\[\([0-9][0-9]*\)\]$/\1/p')
                printf 'fd=%s inode=%s target=%s\n' "$fd" "$inode" "$target"
                if [ -n "$inode" ]; then
                    awk -v inode="$inode" '$10 == inode {print "proc_net_udp " $0}' /proc/net/udp 2>/dev/null || true
                    awk -v inode="$inode" '$10 == inode {print "proc_net_udp6 " $0}' /proc/net/udp6 2>/dev/null || true
                fi
                ;;
        esac
    done
else
    warn "Asterisk file-descriptor metadata was unavailable"
fi

section "OPTIONAL LSOF UDP MAPPING"
if command -v lsof >/dev/null 2>&1 && [ -n "$PID" ]; then
    lsof -nP -a -p "$PID" -iUDP 2>&1 || true
else
    echo "lsof unavailable; /proc and ss mappings above are authoritative"
fi

section "RTP RUNTIME AND CONFIGURED RANGE"
RTP_RUNTIME=$(asterisk -rx 'rtp show settings' 2>&1 || true)
printf '%s\n' "$RTP_RUNTIME"
for file in /etc/asterisk/rtp.conf /etc/asterisk/rtp_additional.conf /etc/asterisk/rtp_custom.conf; do
    safe_config_lines "$file"
done
RTP_START=$(awk -F= '
    /^[[:space:]]*[#;]/ {next}
    /^[[:space:]]*rtpstart[[:space:]]*=/ {gsub(/[[:space:]]/, "", $2); value=$2}
    END {print value}
' /etc/asterisk/rtp.conf /etc/asterisk/rtp_additional.conf /etc/asterisk/rtp_custom.conf 2>/dev/null || true)
RTP_END=$(awk -F= '
    /^[[:space:]]*[#;]/ {next}
    /^[[:space:]]*rtpend[[:space:]]*=/ {gsub(/[[:space:]]/, "", $2); value=$2}
    END {print value}
' /etc/asterisk/rtp.conf /etc/asterisk/rtp_additional.conf /etc/asterisk/rtp_custom.conf 2>/dev/null || true)
case "$RTP_START:$RTP_END" in
    *[!0-9:]*|:|*:) echo "rtp_range=unresolved" ;;
    *) echo "rtp_range=$RTP_START-$RTP_END" ;;
esac

section "KERNEL EPHEMERAL RANGE"
if command -v sysctl >/dev/null 2>&1; then
    EPHEMERAL=$(sysctl -n net.ipv4.ip_local_port_range 2>/dev/null || true)
else
    EPHEMERAL=$(cat /proc/sys/net/ipv4/ip_local_port_range 2>/dev/null || true)
fi
echo "ip_local_port_range=$EPHEMERAL"
EPHEMERAL_START=$(printf '%s\n' "$EPHEMERAL" | awk '{print $1}')
EPHEMERAL_END=$(printf '%s\n' "$EPHEMERAL" | awk '{print $2}')

section "PORT RANGE CLASSIFICATION"
for port in $HIGH_PORTS; do
    classification="outside_configured_ranges"
    if [ -n "$RTP_START" ] && [ -n "$RTP_END" ] &&
       [ "$port" -ge "$RTP_START" ] 2>/dev/null && [ "$port" -le "$RTP_END" ] 2>/dev/null; then
        classification="inside_rtp_range"
    elif [ -n "$EPHEMERAL_START" ] && [ -n "$EPHEMERAL_END" ] &&
         [ "$port" -ge "$EPHEMERAL_START" ] 2>/dev/null && [ "$port" -le "$EPHEMERAL_END" ] 2>/dev/null; then
        classification="inside_kernel_ephemeral_range"
    fi
    echo "port=$port classification=$classification"
done

section "RTP STUN ICE AND RESOLVER MODULES"
asterisk -rx 'module show like res_rtp' 2>&1 || true
asterisk -rx 'module show like res_stun_monitor' 2>&1 || true
asterisk -rx 'module show like res_resolver' 2>&1 || true
asterisk -rx 'module show like res_pjsip' 2>&1 || true
asterisk -rx 'module show like res_http_websocket' 2>&1 || true
for file in /etc/asterisk/res_stun_monitor.conf /etc/asterisk/res_stun_monitor_custom.conf /etc/asterisk/pjsip.conf /etc/asterisk/pjsip.transports.conf /etc/asterisk/pjsip.transports_custom.conf; do
    safe_config_lines "$file"
done

section "NETWORK NAMESPACE AND ROUTING METADATA"
if [ -n "$PID" ]; then
    stat -Lc 'network_namespace_inode=%i path=%n' "/proc/$PID/ns/net" 2>/dev/null || true
fi
ip -brief address show 2>&1 | sed -E 's/[[:space:]]+/ /g' || true
ip route show table main 2>&1 || true
ip -6 route show table main 2>&1 || true

section "CONFIGURATION HASHES"
for file in /etc/asterisk/rtp.conf /etc/asterisk/rtp_additional.conf /etc/asterisk/rtp_custom.conf /etc/asterisk/res_stun_monitor.conf /etc/asterisk/res_stun_monitor_custom.conf /etc/asterisk/pjsip.conf /etc/asterisk/pjsip.transports.conf /etc/asterisk/pjsip.transports_custom.conf; do
    [ -f "$file" ] || continue
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file"
    sha256sum "$file"
done

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No tracer, packet capture, configuration, service, listener, route, certificate, firewall, package, call, logger, container, or traffic change was performed."
