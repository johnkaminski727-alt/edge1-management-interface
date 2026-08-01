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
            echo "Read-only Asterisk file-descriptor origin probe."
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

for command in asterisk awk grep sed ps ss systemctl date hostname id; do
    command -v "$command" >/dev/null 2>&1 || { echo "ERROR missing command: $command" >&2; exit 2; }
done

warnings=0
failures=0
warn() { warnings=$((warnings + 1)); echo "WARNING: $*"; }
fail() { failures=$((failures + 1)); echo "FAIL: $*"; }
section() { echo; echo "=== $* ==="; }

valid_asterisk_pid() {
    candidate=$1
    case "$candidate" in
        ''|0|*[!0-9]*) return 1 ;;
    esac
    [ -r "/proc/$candidate/comm" ] || return 1
    [ "$(sed -n '1p' "/proc/$candidate/comm" 2>/dev/null)" = "asterisk" ] || return 1
    return 0
}

resolve_asterisk_pid() {
    candidate=$(systemctl show -p MainPID --value asterisk 2>/dev/null || true)
    if valid_asterisk_pid "$candidate"; then
        PID_RESOLVED=$candidate
        PID_SOURCE="systemd:MainPID"
        return 0
    fi

    for pidfile in /run/asterisk/asterisk.pid /var/run/asterisk/asterisk.pid; do
        [ -r "$pidfile" ] || continue
        candidate=$(awk 'NR == 1 {print $1; exit}' "$pidfile" 2>/dev/null || true)
        if valid_asterisk_pid "$candidate"; then
            PID_RESOLVED=$candidate
            PID_SOURCE="pidfile:$pidfile"
            return 0
        fi
    done

    matches=$(ps -eo pid=,comm=,args= 2>/dev/null |
        awk '$2 == "asterisk" && $0 ~ /(^|[[:space:]])-f([[:space:]]|$)/ {print $1}')
    count=$(printf '%s\n' "$matches" | awk 'NF {count++} END {print count + 0}')
    if [ "$count" -eq 1 ]; then
        candidate=$(printf '%s\n' "$matches" | awk 'NF {print; exit}')
        if valid_asterisk_pid "$candidate"; then
            PID_RESOLVED=$candidate
            PID_SOURCE="process-table:unique-asterisk-f"
            return 0
        fi
    fi
    return 1
}

echo "WW.CX ASTERISK FILE-DESCRIPTOR ORIGIN PROBE"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no tracer attachment, packet capture, configuration, service, listener, route, certificate, firewall, package, call, logger, module, or traffic change"

section "CORE STATE"
asterisk -rx 'core show version' 2>&1 || true
asterisk -rx 'core show uptime' 2>&1 || true
asterisk -rx 'core show channels count' 2>&1 || true
echo "service_active=$(systemctl is-active asterisk 2>&1 || true)"
PID_SOURCE=""
PID_RESOLVED=""
if resolve_asterisk_pid; then
    PID=$PID_RESOLVED
    echo "asterisk_pid=$PID"
    echo "pid_source=$PID_SOURCE"
    ps -p "$PID" -o pid=,lstart=,etime=,args= 2>/dev/null || true
else
    PID=""
    fail "Unable to resolve one validated Asterisk PID"
fi

section "TARGET UDP SOCKETS"
if [ -n "$PID" ]; then
    ss -H -lunpe 2>&1 | grep "pid=$PID" | grep -E ':(55539|59177|5061)[[:space:]]' || true
fi

section "CORE SHOW FD AVAILABILITY"
FD_HELP=$(asterisk -rx 'core show help core show fd' 2>&1 || true)
printf '%s\n' "$FD_HELP"
if printf '%s\n' "$FD_HELP" | grep -Eqi 'No such command|not available|not found'; then
    FD_AVAILABLE=no
    warn "core show fd is unavailable; this build likely lacks DEBUG_FD_LEAKS"
elif printf '%s\n' "$FD_HELP" | grep -Eqi 'file descriptor|open by Asterisk|Usage:[[:space:]]*core show fd'; then
    FD_AVAILABLE=yes
else
    FD_AVAILABLE=unknown
    warn "core show fd availability was inconclusive"
fi
echo "core_show_fd_available=$FD_AVAILABLE"

section "TARGET FD CREATION RECORDS"
if [ "$FD_AVAILABLE" = "yes" ]; then
    FD_OUTPUT=$(asterisk -rx 'core show fd' 2>&1 || true)
    printf '%s\n' "$FD_OUTPUT" | awk '
        /^[[:space:]]*(15|17|18)[[:space:]]/ {print; found=1}
        END {if (!found) print "No target FD creation records were returned"}
    '
else
    echo "Skipped because core show fd is unavailable or inconclusive"
fi

section "SAFE PROC FDINFO"
if [ -n "$PID" ]; then
    for fd in 15 17 18; do
        path="/proc/$PID/fdinfo/$fd"
        echo "fd=$fd path=$path"
        if [ -r "$path" ]; then
            awk '/^(pos|flags|mnt_id|ino):/ {print}' "$path"
        else
            warn "FD $fd metadata is unavailable"
        fi
    done
fi

section "RESOLVER AND MEDIA THREAD CORRELATION"
THREADS=$(asterisk -rx 'core show threads' 2>&1 || true)
printf '%s\n' "$THREADS" |
    grep -Ei 'unbound|resolver|dns|rtp|stun|pjsip|websocket' ||
    echo "No resolver/media keyword matches were returned by core show threads"

section "MODULE CORRELATION"
asterisk -rx 'module show like res_resolver_unbound' 2>&1 || true
asterisk -rx 'module show like res_rtp_asterisk' 2>&1 || true
asterisk -rx 'module show like res_stun_monitor' 2>&1 || true
asterisk -rx 'module show like res_pjsip' 2>&1 || true

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Probe state: FAILED"
    exit 1
fi
echo "Probe state: READ-ONLY REVIEW COMPLETE"
echo "No tracer, packet capture, configuration, service, listener, route, certificate, firewall, package, call, logger, module, container, or traffic change was performed."
