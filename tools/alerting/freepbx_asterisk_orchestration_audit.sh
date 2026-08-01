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
            echo "Read-only attribution of FreePBX and Asterisk start, stop, restart and supervision contracts."
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

for command in asterisk awk basename date find grep hostname id ps readlink sed sha256sum sort stat systemctl; do
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
        ASTERISK_PID=$candidate
        ASTERISK_PID_SOURCE="systemd:MainPID"
        return 0
    fi
    for pidfile in /run/asterisk/asterisk.pid /var/run/asterisk/asterisk.pid; do
        [ -r "$pidfile" ] || continue
        candidate=$(awk 'NR == 1 {print $1; exit}' "$pidfile" 2>/dev/null || true)
        if valid_asterisk_pid "$candidate"; then
            ASTERISK_PID=$candidate
            ASTERISK_PID_SOURCE="pidfile:$pidfile"
            return 0
        fi
    done
    return 1
}

echo "WW.CX FREEPBX ASTERISK ORCHESTRATION AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no service, process, PM2, session, cgroup, boot, unit, configuration, listener, firewall, package, call, database, or traffic change"

section "CORE HEALTH AND LIVE OWNERSHIP"
asterisk -rx 'core show version' 2>&1 || true
asterisk -rx 'core show uptime' 2>&1 || true
asterisk -rx 'core show channels count' 2>&1 || true
ASTERISK_PID=""
ASTERISK_PID_SOURCE=""
if resolve_asterisk_pid; then
    echo "asterisk_pid=$ASTERISK_PID"
    echo "pid_source=$ASTERISK_PID_SOURCE"
    ps -p "$ASTERISK_PID" -o pid=,ppid=,pgid=,sid=,lstart=,etime=,user=,group=,stat=,comm=,args= 2>&1 || true
    echo "process_cgroup=$(awk -F: '$1 == "0" {print $3; exit}' "/proc/$ASTERISK_PID/cgroup" 2>/dev/null || true)"
    echo "parent_chain:"
    current=$ASTERISK_PID
    depth=0
    while [ "$depth" -lt 8 ]; do
        ps -p "$current" -o pid=,ppid=,user=,group=,stat=,comm=,args= 2>/dev/null || break
        parent=$(ps -p "$current" -o ppid= 2>/dev/null | awk '{print $1}')
        case "$parent" in
            ''|0|*[!0-9]*) break ;;
        esac
        [ "$parent" -ne "$current" ] || break
        current=$parent
        depth=$((depth + 1))
    done
else
    fail "Unable to resolve one validated live Asterisk PID"
fi

section "ASTERISK UNIT CONTRACT"
systemctl show asterisk.service \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p SourcePath -p Type -p MainPID -p ControlGroup \
    -p ExecStart -p ExecStop -p ExecReload -p Restart -p RemainAfterExit \
    -p Requires -p Wants -p After -p Before -p Conflicts 2>&1 || true
systemctl status asterisk.service --no-pager --lines=0 2>&1 || true
systemctl cat asterisk.service 2>&1 | sed -n '1,280p' || true

section "FREEPBX UNIT CONTRACT"
systemctl show freepbx.service \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p SourcePath -p Type -p MainPID -p ControlGroup \
    -p ExecStart -p ExecStop -p Restart -p RemainAfterExit \
    -p Requires -p Wants -p After -p Before -p Conflicts 2>&1 || true
systemctl status freepbx.service --no-pager --lines=0 2>&1 || true
systemctl cat freepbx.service 2>&1 | sed -n '1,280p' || true

echo "freepbx_reverse_dependencies:"
systemctl list-dependencies --reverse freepbx.service --no-pager 2>&1 | sed -n '1,220p' || true
echo "asterisk_reverse_dependencies:"
systemctl list-dependencies --reverse asterisk.service --no-pager 2>&1 | sed -n '1,220p' || true

section "FWCONSOLE ENTRYPOINT"
FWCONSOLE=$(command -v fwconsole 2>/dev/null || true)
echo "fwconsole_path=${FWCONSOLE:-missing}"
if [ -n "$FWCONSOLE" ] && [ -e "$FWCONSOLE" ]; then
    FWCONSOLE_REAL=$(readlink -f "$FWCONSOLE" 2>/dev/null || true)
    echo "fwconsole_realpath=${FWCONSOLE_REAL:-unresolved}"
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$FWCONSOLE" 2>&1 || true
    [ -n "$FWCONSOLE_REAL" ] && stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$FWCONSOLE_REAL" 2>&1 || true
    [ -n "$FWCONSOLE_REAL" ] && [ -f "$FWCONSOLE_REAL" ] && sha256sum "$FWCONSOLE_REAL" 2>&1 || true
else
    fail "fwconsole entrypoint is missing"
fi

section "FREEPBX ORCHESTRATION SOURCE REFERENCES"
reference_count=0
for root in \
    /var/www/html/admin/libraries/Console \
    /var/www/html/admin/libraries/BMO \
    /var/www/html/admin/modules/core \
    /var/www/html/admin/modules/framework \
    /var/www/html/admin/bootstrap.php; do
    [ -e "$root" ] || continue
    echo "reference_root=$root"
    matches=$(grep -RnsE \
        --include='*.php' --include='*.inc' --include='*.sh' --include='*.service' \
        'safe_asterisk|/usr/sbin/asterisk|asterisk[[:space:]]+-f|fwconsole[[:space:]]+(start|stop|restart|reload)|(^|[^[:alnum:]_])(start|stop|restart|reload)Asterisk|Asterisk[^[:alnum:]_]+(start|stop|restart|reload)' \
        "$root" 2>/dev/null | sed -n '1,360p' || true)
    if [ -n "$matches" ]; then
        printf '%s\n' "$matches"
        reference_count=$((reference_count + 1))
    fi
done
echo "orchestration_reference_roots_with_matches=$reference_count"

section "INIT AND SAFE_ASTERISK START PATHS"
for file in /etc/init.d/asterisk /usr/sbin/safe_asterisk; do
    [ -f "$file" ] || continue
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" 2>&1 || true
    sha256sum "$file" 2>&1 || true
    grep -nE 'start-stop-daemon|safe_asterisk|/usr/sbin/asterisk|ASTSBINDIR|DAEMON=|run_asterisk|while[[:space:]]*:' "$file" 2>/dev/null |
        sed -n '1,260p' || true
done

section "FREEPBX CHILD PROCESS INVENTORY"
FREEPBX_CGROUP=$(systemctl show -p ControlGroup --value freepbx.service 2>/dev/null || true)
echo "freepbx_control_group=${FREEPBX_CGROUP:-none}"
if [ -n "$FREEPBX_CGROUP" ] && [ -d "/sys/fs/cgroup$FREEPBX_CGROUP" ]; then
    if [ -r "/sys/fs/cgroup$FREEPBX_CGROUP/cgroup.procs" ]; then
        for pid in $(sort -n -u "/sys/fs/cgroup$FREEPBX_CGROUP/cgroup.procs" 2>/dev/null); do
            [ -r "/proc/$pid/comm" ] || continue
            ps -p "$pid" -o pid=,ppid=,lstart=,etime=,user=,group=,stat=,comm= 2>&1 || true
            echo "pid_${pid}_exe=$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
            echo "pid_${pid}_cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
        done
    fi
else
    warn "freepbx.service cgroup is missing or unresolved"
fi

section "ORCHESTRATION CLASSIFICATION"
ASTERISK_MAINPID=$(systemctl show -p MainPID --value asterisk.service 2>/dev/null || true)
ASTERISK_CGROUP=$(systemctl show -p ControlGroup --value asterisk.service 2>/dev/null || true)
FREEPBX_REQUIRES=$(systemctl show -p Requires --value freepbx.service 2>/dev/null || true)
FREEPBX_WANTS=$(systemctl show -p Wants --value freepbx.service 2>/dev/null || true)
FREEPBX_AFTER=$(systemctl show -p After --value freepbx.service 2>/dev/null || true)

case "$ASTERISK_MAINPID" in
    ''|0|*[!0-9]*) warn "asterisk.service does not own a usable MainPID" ;;
esac
[ -n "$ASTERISK_CGROUP" ] || warn "asterisk.service has no system service cgroup"
case " $FREEPBX_REQUIRES $FREEPBX_WANTS $FREEPBX_AFTER " in
    *' asterisk.service '*) echo "freepbx_declares_asterisk_relationship=yes" ;;
    *)
        echo "freepbx_declares_asterisk_relationship=no"
        warn "freepbx.service has no explicit captured dependency or ordering relationship with asterisk.service"
        ;;
esac
if [ -n "$ASTERISK_PID_SOURCE" ] && [ "$ASTERISK_PID_SOURCE" != "systemd:MainPID" ]; then
    warn "Live Asterisk PID resolution depends on $ASTERISK_PID_SOURCE rather than systemd"
fi
if [ "$reference_count" -eq 0 ]; then
    warn "No FreePBX source reference to Asterisk orchestration was found in the bounded search roots"
fi

echo "native_service_design_gates:"
echo "- determine whether fwconsole start or stop directly controls Asterisk"
echo "- choose one long-running supervisor: systemd or safe_asterisk, not both"
echo "- express FreePBX and Asterisk ordering explicitly"
echo "- preserve PM2 and FreePBX child behavior separately from Asterisk ownership"
echo "- require a controlled outage, rollback and post-start CLI/listener verification before activation"

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No service, process, PM2, session, cgroup, boot, unit, configuration, listener, firewall, package, call, database, logger, module, container, or traffic change was performed."
