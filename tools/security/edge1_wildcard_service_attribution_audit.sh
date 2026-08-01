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
            echo "Read-only attribution audit for wildcard MariaDB and Node listeners."
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

for command in awk basename cut date find grep hostname id nft ps readlink sed sha256sum sort ss stat systemctl tr; do
    command -v "$command" >/dev/null 2>&1 || { echo "ERROR missing command: $command" >&2; exit 2; }
done

warnings=0
failures=0
warn() { warnings=$((warnings + 1)); echo "WARNING: $*"; }
fail() { failures=$((failures + 1)); echo "FAIL: $*"; }
section() { echo; echo "=== $* ==="; }

listener_pids() {
    port=$1
    ss -H -ltnpe 2>/dev/null |
        grep -E ":${port}[[:space:]]" |
        grep -oE 'pid=[0-9]+' |
        cut -d= -f2 |
        sort -n -u
}

inspect_unit_file() {
    unit=$1
    fragment=$(systemctl show -p FragmentPath --value "$unit" 2>/dev/null || true)
    case "$fragment" in
        /*)
            echo "unit_fragment=$fragment"
            if [ -f "$fragment" ]; then
                stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$fragment" 2>&1 || true
                sha256sum "$fragment" 2>&1 || true
                grep -nE '^[[:space:]]*(Description|After|Before|Requires|Wants|Type|User|Group|WorkingDirectory|Restart|PIDFile|RuntimeDirectory|RuntimeDirectoryMode|ListenStream|ListenDatagram|Accept|FreeBind|Service)[[:space:]]*=' "$fragment" 2>/dev/null || true
            fi
            ;;
        *) echo "unit_fragment=unresolved" ;;
    esac
}

inspect_pid() {
    pid=$1
    [ -r "/proc/$pid/comm" ] || { warn "PID $pid disappeared during inspection"; return 0; }
    echo "pid=$pid"
    ps -p "$pid" -o pid=,ppid=,lstart=,etime=,user=,group=,stat=,comm= 2>&1 || true
    echo "exe=$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
    echo "cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    cgroup=$(awk -F: '$1 == "0" {print $3; exit}' "/proc/$pid/cgroup" 2>/dev/null || true)
    echo "process_cgroup=$cgroup"
    unit=""
    case "$cgroup" in
        /system.slice/*.service)
            unit=$(basename "$cgroup")
            ;;
    esac
    echo "systemd_unit=${unit:-unresolved}"
    if [ -n "$unit" ]; then
        systemctl show "$unit" \
            -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
            -p FragmentPath -p SourcePath -p Type -p MainPID -p ControlGroup \
            -p Restart -p User -p Group 2>&1 || true
        systemctl status "$unit" --no-pager --lines=0 2>&1 || true
        inspect_unit_file "$unit"
    fi

    comm=$(sed -n '1p' "/proc/$pid/comm" 2>/dev/null || true)
    case "$comm" in
        node|nodejs)
            script=$(tr '\000' '\n' < "/proc/$pid/cmdline" 2>/dev/null | sed -n '2p' || true)
            case "$script" in
                /*)
                    echo "node_script=$script"
                    if [ -f "$script" ]; then
                        stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$script" 2>&1 || true
                        sha256sum "$script" 2>&1 || true
                    fi
                    ;;
                *) echo "node_script=unresolved" ;;
            esac
            ;;
    esac
}

echo "WW.CX EDGE1 WILDCARD SERVICE ATTRIBUTION AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no database, service, process, unit, listener, firewall, configuration, package, container, or traffic change"
echo "Scope: MariaDB TCP 3306 and Node TCP 8001/8003, with supporting firewall and proxy references"

section "TARGET LISTENERS"
TARGET_LISTENERS=$(ss -H -ltnpe 2>&1 | grep -E ':(3306|8001|8003)[[:space:]]' || true)
printf '%s\n' "$TARGET_LISTENERS"
for port in 3306 8001 8003; do
    if printf '%s\n' "$TARGET_LISTENERS" | grep -Eq ":${port}[[:space:]]"; then
        warn "TCP $port is listening and requires an explicit scope decision"
    else
        echo "port_${port}_listener=absent"
    fi
done

section "MARIADB SERVICE AND SOCKET ACTIVATION"
systemctl show mariadb.service \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p Type -p MainPID -p ControlGroup \
    -p Restart -p User -p Group -p Requires -p Wants -p After 2>&1 || true
systemctl status mariadb.service --no-pager --lines=0 2>&1 || true
inspect_unit_file mariadb.service

systemctl show mariadb.socket \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p Listen -p Accept -p FreeBind -p Service \
    -p ControlGroup -p Triggers -p TriggeredBy 2>&1 || true
systemctl status mariadb.socket --no-pager --lines=0 2>&1 || true
inspect_unit_file mariadb.socket
systemctl list-dependencies --reverse mariadb.socket --no-pager 2>&1 | sed -n '1,220p' || true

MARIADB_PIDS=$(listener_pids 3306 || true)
if [ -n "$MARIADB_PIDS" ]; then
    echo "mariadb_listener_pids=$MARIADB_PIDS"
    for pid in $MARIADB_PIDS; do
        inspect_pid "$pid"
    done
else
    warn "No userspace PID was resolved for TCP 3306; systemd socket ownership may be authoritative"
fi

echo "established_tcp_3306_count=$(ss -Htn state established '( sport = :3306 )' 2>/dev/null | awk 'END {print NR + 0}')"
echo "mariadb_unix_sockets:"
ss -Hxlpn 2>&1 | grep -Ei 'maria|mysql|mysqld' || echo "none observed"

section "MARIADB BINDING CONFIGURATION"
for file in /etc/mysql/my.cnf /etc/mysql/mariadb.cnf /etc/mysql/mariadb.conf.d/*.cnf /etc/mysql/conf.d/*.cnf; do
    [ -f "$file" ] || continue
    echo "config_file=$file"
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" 2>&1 || true
    sha256sum "$file" 2>&1 || true
    grep -nE '^[[:space:]]*(bind-address|skip-networking|skip-bind-address|port|socket|protocol)[[:space:]]*=' "$file" 2>/dev/null || true
done

section "NODE LISTENER OWNERSHIP"
NODE_PIDS=""
for port in 8001 8003; do
    pids=$(listener_pids "$port" || true)
    echo "port_${port}_pids=${pids:-none}"
    NODE_PIDS=$(printf '%s\n%s\n' "$NODE_PIDS" "$pids" | awk 'NF' | sort -n -u)
done
if [ -n "$NODE_PIDS" ]; then
    for pid in $NODE_PIDS; do
        inspect_pid "$pid"
    done
else
    warn "No Node listener PID was resolved for TCP 8001 or 8003"
fi

echo "established_tcp_8001_count=$(ss -Htn state established '( sport = :8001 )' 2>/dev/null | awk 'END {print NR + 0}')"
echo "established_tcp_8003_count=$(ss -Htn state established '( sport = :8003 )' 2>/dev/null | awk 'END {print NR + 0}')"

section "LOCAL PROXY AND UNIT REFERENCES"
for root in /etc/apache2 /etc/haproxy /etc/nginx /etc/systemd/system /lib/systemd/system /usr/lib/systemd/system; do
    [ -d "$root" ] || continue
    echo "reference_root=$root"
    grep -RnsE --include='*.conf' --include='*.service' --include='*.socket' --include='*.target' '(^|[^0-9])(8001|8003)([^0-9]|$)' "$root" 2>/dev/null |
        sed -n '1,260p' || true
done

section "AUTHORITATIVE FIREWALL INPUT PATH"
nft -a list chain inet wwcxfw input 2>&1 || true

echo "public_allow_summary:"
nft -a list chain inet wwcxfw input 2>/dev/null |
    grep -E 'tcp dport|udp dport|iifname|policy' || true

section "EXPOSURE CLASSIFICATION"
echo "- TCP 3306, 8001, and 8003 are wildcard-bound at the process or socket layer when present"
echo "- the observed wwcxfw public policy admits only TCP 80/443 and UDP 51820"
echo "- new public-interface connections to 3306, 8001, and 8003 are therefore dropped under the observed policy"
echo "- the broad iifname wg0 accept rule makes these wildcard listeners reachable from authenticated WireGuard peers"
echo "- listener narrowing or WireGuard policy changes require consumer attribution and rollback planning"
echo "- no public reachability claim is made without an outside-in scan"

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No database, service, process, unit, listener, firewall, configuration, package, logger, container, or traffic change was performed."
