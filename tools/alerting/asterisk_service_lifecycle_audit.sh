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
            echo "Read-only audit of Asterisk service, PID, cgroup, session, and boot ownership."
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

for command in asterisk awk basename date find grep hostname id loginctl ps readlink sed sha256sum stat systemctl; do
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

echo "WW.CX ASTERISK SERVICE LIFECYCLE AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no service, process, session, cgroup, boot, configuration, listener, firewall, package, call, or traffic change"

section "CORE STATE"
asterisk -rx 'core show version' 2>&1 || true
asterisk -rx 'core show uptime' 2>&1 || true
asterisk -rx 'core show channels count' 2>&1 || true
echo "service_active=$(systemctl is-active asterisk 2>&1 || true)"
echo "service_enabled=$(systemctl is-enabled asterisk 2>&1 || true)"
PID_SOURCE=""
PID_RESOLVED=""
if resolve_asterisk_pid; then
    PID=$PID_RESOLVED
    echo "asterisk_pid=$PID"
    echo "pid_source=$PID_SOURCE"
else
    PID=""
    fail "Unable to resolve one validated Asterisk PID"
fi

section "SYSTEMD UNIT IDENTITY"
systemctl show asterisk \
    -p Id \
    -p Names \
    -p LoadState \
    -p ActiveState \
    -p SubState \
    -p UnitFileState \
    -p FragmentPath \
    -p SourcePath \
    -p Type \
    -p GuessMainPID \
    -p RemainAfterExit \
    -p MainPID \
    -p ControlPID \
    -p ControlGroup \
    -p ExecMainPID \
    -p ExecMainStatus \
    -p Result \
    -p InvocationID 2>&1 || true
systemctl status asterisk --no-pager --lines=30 2>&1 || true

echo "--- unit definition ---"
systemctl cat asterisk 2>&1 | sed -n '1,240p' || true

SYSTEMD_MAINPID=$(systemctl show -p MainPID --value asterisk 2>/dev/null || true)
SYSTEMD_CGROUP=$(systemctl show -p ControlGroup --value asterisk 2>/dev/null || true)
SYSTEMD_ACTIVE=$(systemctl is-active asterisk 2>/dev/null || true)

section "PROCESS OWNERSHIP"
if [ -n "$PID" ]; then
    ps -p "$PID" -o pid=,ppid=,pgid=,sid=,lstart=,etime=,user=,group=,stat=,args= 2>&1 || true
    echo "exe=$(readlink -f "/proc/$PID/exe" 2>/dev/null || true)"
    echo "cwd=$(readlink -f "/proc/$PID/cwd" 2>/dev/null || true)"
    echo "cgroup_records:"
    sed -n '1,40p' "/proc/$PID/cgroup" 2>/dev/null || true

    echo "parent_chain:"
    current=$PID
    depth=0
    while [ "$depth" -lt 8 ]; do
        ps -p "$current" -o pid=,ppid=,user=,stat=,comm=,args= 2>/dev/null || break
        parent=$(ps -p "$current" -o ppid= 2>/dev/null | awk '{print $1}')
        case "$parent" in
            ''|0|*[!0-9]*) break ;;
        esac
        [ "$parent" -ne "$current" ] || break
        current=$parent
        depth=$((depth + 1))
    done
fi

section "PID FILE METADATA"
for pidfile in /run/asterisk/asterisk.pid /var/run/asterisk/asterisk.pid; do
    [ -e "$pidfile" ] || continue
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$pidfile" 2>&1 || true
    awk 'NR == 1 && $1 ~ /^[0-9]+$/ {print "pidfile_value=" $1}' "$pidfile" 2>/dev/null || true
done

section "CGROUP AND LOGIN SESSION"
PROCESS_CGROUP=""
SCOPE_UNIT=""
SESSION_ID=""
if [ -n "$PID" ]; then
    PROCESS_CGROUP=$(awk -F: '$1 == "0" {print $3; exit}' "/proc/$PID/cgroup" 2>/dev/null || true)
    echo "process_cgroup=$PROCESS_CGROUP"
    SCOPE_UNIT=$(basename "$PROCESS_CGROUP" 2>/dev/null || true)
    echo "scope_unit=$SCOPE_UNIT"
    case "$SCOPE_UNIT" in
        session-*.scope)
            SESSION_ID=$(printf '%s\n' "$SCOPE_UNIT" | sed -n 's/^session-\([0-9][0-9]*\)\.scope$/\1/p')
            ;;
    esac
fi

echo "systemd_control_group=$SYSTEMD_CGROUP"
if [ -n "$SCOPE_UNIT" ]; then
    systemctl show "$SCOPE_UNIT" \
        -p Id -p LoadState -p ActiveState -p SubState -p ControlGroup -p Slice -p User -p Leader 2>&1 || true
fi
if [ -n "$SESSION_ID" ]; then
    loginctl show-session "$SESSION_ID" \
        -p Id -p User -p Name -p Service -p Type -p Class -p State -p Leader -p Scope -p IdleHint 2>&1 || true
fi

PROCESS_UID=""
if [ -n "$PID" ] && [ -r "/proc/$PID/status" ]; then
    PROCESS_UID=$(awk '/^Uid:/ {print $2; exit}' "/proc/$PID/status" 2>/dev/null || true)
fi
case "$PROCESS_UID" in
    ''|*[!0-9]*) ;;
    *) loginctl show-user "$PROCESS_UID" -p UID -p Name -p State -p Linger -p Sessions -p Display 2>&1 || true ;;
esac

section "LOGIN SESSION POLICY"
for file in /etc/systemd/logind.conf /etc/systemd/logind.conf.d/*.conf; do
    [ -f "$file" ] || continue
    echo "source=$file"
    grep -E '^[[:space:]]*(KillUserProcesses|KillOnlyUsers|KillExcludeUsers|RemoveIPC)[[:space:]]*=' "$file" 2>/dev/null || true
done
loginctl show-logind -p KillUserProcesses -p KillOnlyUsers -p KillExcludeUsers -p RemoveIPC 2>&1 || true

section "BOOT REGISTRATION"
systemctl list-unit-files 'asterisk.service' --no-pager 2>&1 || true
if [ -f /etc/init.d/asterisk ]; then
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' /etc/init.d/asterisk
    sha256sum /etc/init.d/asterisk
fi
for dir in /etc/rc0.d /etc/rc1.d /etc/rc2.d /etc/rc3.d /etc/rc4.d /etc/rc5.d /etc/rc6.d /etc/rcS.d; do
    [ -d "$dir" ] || continue
    find "$dir" -maxdepth 1 -type l -name '*asterisk*' -printf '%p -> %l\n' 2>/dev/null || true
done

section "LIFECYCLE CLASSIFICATION"
if [ "$SYSTEMD_ACTIVE" = "active" ]; then
    case "$SYSTEMD_MAINPID" in
        ''|0|*[!0-9]*) warn "asterisk.service is active but systemd does not own a usable MainPID" ;;
    esac
fi
if [ -n "$PID_SOURCE" ] && [ "$PID_SOURCE" != "systemd:MainPID" ]; then
    warn "The live Asterisk PID was resolved through $PID_SOURCE rather than systemd MainPID"
fi
case "$PROCESS_CGROUP" in
    /user.slice/*) warn "The Asterisk process is attached to a user-session cgroup rather than a system service cgroup" ;;
esac
if [ -n "$SYSTEMD_CGROUP" ] && [ -n "$PROCESS_CGROUP" ]; then
    case "$PROCESS_CGROUP" in
        "$SYSTEMD_CGROUP"|"$SYSTEMD_CGROUP"/*) ;;
        *) warn "The live process cgroup does not match the asterisk.service ControlGroup" ;;
    esac
fi
if [ -z "$SYSTEMD_CGROUP" ]; then
    warn "asterisk.service reports no systemd ControlGroup"
fi

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No service, process, session, cgroup, boot, configuration, listener, firewall, package, call, logger, module, container, or traffic change was performed."
