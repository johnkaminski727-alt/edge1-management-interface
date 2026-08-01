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
            echo "Read-only preflight for an Asterisk native-systemd service design."
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

for command in asterisk awk basename date find grep hostname id ps readlink sed sha256sum stat systemctl; do
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

echo "WW.CX ASTERISK NATIVE SERVICE MIGRATION PREFLIGHT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no service, process, session, cgroup, boot, unit, configuration, listener, firewall, package, call, or traffic change"

section "CORE HEALTH"
asterisk -rx 'core show version' 2>&1 || true
asterisk -rx 'core show uptime' 2>&1 || true
asterisk -rx 'core show channels count' 2>&1 || true
PID_SOURCE=""
PID_RESOLVED=""
if resolve_asterisk_pid; then
    PID=$PID_RESOLVED
    echo "asterisk_pid=$PID"
    echo "pid_source=$PID_SOURCE"
    ps -p "$PID" -o pid=,ppid=,pgid=,sid=,lstart=,etime=,user=,group=,stat=,args= 2>&1 || true
else
    PID=""
    fail "Unable to resolve one validated Asterisk PID"
fi

section "CURRENT ASTERISK UNIT CONTRACT"
systemctl show asterisk \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p SourcePath -p Type -p GuessMainPID \
    -p RemainAfterExit -p Restart -p MainPID -p ControlPID \
    -p ControlGroup -p ExecMainPID -p ExecMainStatus -p Result 2>&1 || true
systemctl status asterisk --no-pager --lines=0 2>&1 || true
systemctl cat asterisk 2>&1 | sed -n '1,240p' || true

section "INIT SCRIPT CONTRACT"
if [ -f /etc/init.d/asterisk ]; then
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' /etc/init.d/asterisk
    sha256sum /etc/init.d/asterisk
    grep -nE 'safe_asterisk|AST_(USER|GROUP|PID|SBIN)|PIDFILE|start-stop-daemon|killproc|daemon|^[[:space:]]*(start|stop|restart|reload|status)\)' /etc/init.d/asterisk 2>/dev/null |
        sed -n '1,260p' || true
else
    fail "/etc/init.d/asterisk is missing"
fi

section "SAFE_ASTERISK CONTRACT"
if [ -f /usr/sbin/safe_asterisk ]; then
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' /usr/sbin/safe_asterisk
    sha256sum /usr/sbin/safe_asterisk
    grep -nE 'AST_(USER|GROUP|PID)|PIDFILE|asterisk|runuser|su[[:space:]]|exec|trap|while|sleep' /usr/sbin/safe_asterisk 2>/dev/null |
        sed -n '1,260p' || true
else
    warn "/usr/sbin/safe_asterisk is missing"
fi

section "ASTERISK RUNTIME PATHS AND IDENTITY"
if [ -f /etc/asterisk/asterisk.conf ]; then
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' /etc/asterisk/asterisk.conf
    sha256sum /etc/asterisk/asterisk.conf
    grep -nE '^[[:space:]]*(runuser|rungroup|astetcdir|astmoddir|astvarlibdir|astdbdir|astkeydir|astdatadir|astagidir|astspooldir|astrundir|astlogdir|astsbindir)[[:space:]]*=>' /etc/asterisk/asterisk.conf 2>/dev/null || true
fi
for path in /run/asterisk /var/run/asterisk /var/log/asterisk /var/lib/asterisk /var/spool/asterisk; do
    [ -e "$path" ] || continue
    stat -c 'mode=%a owner=%U group=%G path=%n' "$path" 2>&1 || true
done

section "FREEPBX SERVICE RELATIONSHIP"
echo "fwconsole_path=$(command -v fwconsole 2>/dev/null || true)"
systemctl show freepbx \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p SourcePath -p Type -p MainPID -p ControlGroup \
    -p Requires -p Wants -p After -p Before -p Conflicts 2>&1 || true
systemctl status freepbx --no-pager --lines=0 2>&1 || true
systemctl cat freepbx 2>&1 | sed -n '1,260p' || true

section "EXISTING NATIVE UNIT CANDIDATES"
found_native=0
for unit in /etc/systemd/system/asterisk.service /lib/systemd/system/asterisk.service /usr/lib/systemd/system/asterisk.service; do
    [ -f "$unit" ] || continue
    found_native=1
    echo "unit_candidate=$unit"
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$unit"
    sha256sum "$unit"
    sed -n '1,260p' "$unit"
done
if [ "$found_native" -eq 0 ]; then
    echo "native_unit_candidate=none"
fi

section "SERVICE DEPENDENCIES"
systemctl list-dependencies asterisk.service --no-pager 2>&1 | sed -n '1,240p' || true
systemctl list-dependencies --reverse asterisk.service --no-pager 2>&1 | sed -n '1,240p' || true
systemctl list-dependencies freepbx.service --no-pager 2>&1 | sed -n '1,240p' || true
systemctl list-dependencies --reverse freepbx.service --no-pager 2>&1 | sed -n '1,240p' || true

section "LIVE PROCESS OWNERSHIP"
PROCESS_CGROUP=""
if [ -n "$PID" ]; then
    echo "exe=$(readlink -f "/proc/$PID/exe" 2>/dev/null || true)"
    echo "cwd=$(readlink -f "/proc/$PID/cwd" 2>/dev/null || true)"
    PROCESS_CGROUP=$(awk -F: '$1 == "0" {print $3; exit}' "/proc/$PID/cgroup" 2>/dev/null || true)
    echo "process_cgroup=$PROCESS_CGROUP"
    echo "parent_chain:"
    current=$PID
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
fi

section "MIGRATION REQUIREMENT CLASSIFICATION"
UNIT_FRAGMENT=$(systemctl show -p FragmentPath --value asterisk 2>/dev/null || true)
UNIT_SOURCE=$(systemctl show -p SourcePath --value asterisk 2>/dev/null || true)
UNIT_MAINPID=$(systemctl show -p MainPID --value asterisk 2>/dev/null || true)
UNIT_CGROUP=$(systemctl show -p ControlGroup --value asterisk 2>/dev/null || true)
UNIT_SUBSTATE=$(systemctl show -p SubState --value asterisk 2>/dev/null || true)

case "$UNIT_FRAGMENT" in
    /run/systemd/generator*/*) warn "Asterisk is managed through a generated SysV compatibility unit" ;;
esac
case "$UNIT_SOURCE" in
    /etc/init.d/asterisk) warn "The active service contract is the legacy init script" ;;
esac
case "$UNIT_MAINPID" in
    ''|0|*[!0-9]*) warn "systemd does not own a usable Asterisk MainPID" ;;
esac
[ -n "$UNIT_CGROUP" ] || warn "asterisk.service has no systemd ControlGroup"
[ "$UNIT_SUBSTATE" = "running" ] || warn "asterisk.service is not in running substate"
case "$PROCESS_CGROUP" in
    /user.slice/*) warn "The live Asterisk process remains attached to a user-session cgroup" ;;
esac
if [ -n "$PID_SOURCE" ] && [ "$PID_SOURCE" != "systemd:MainPID" ]; then
    warn "Live PID resolution depends on $PID_SOURCE rather than systemd"
fi

echo "required_native_unit_properties:"
echo "- systemd must directly own the long-running Asterisk or safe_asterisk process"
echo "- MainPID and ControlGroup must be non-empty and match the live daemon"
echo "- start, stop, reload, PID-file, user, group, runtime-directory, and FreePBX expectations must be preserved"
echo "- deployment must include rollback to the existing SysV contract"
echo "- activation requires a controlled outage window and post-start CLI/listener validation"
echo "- no candidate unit is approved solely by this preflight"

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No service, process, session, cgroup, boot, unit, configuration, listener, firewall, package, call, logger, module, container, or traffic change was performed."
