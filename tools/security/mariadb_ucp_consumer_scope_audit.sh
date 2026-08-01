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
            echo "Read-only consumer and scope audit for MariaDB TCP 3306 and FreePBX UCP TCP 8001/8003."
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

for command in awk basename date find grep hostname id nft ps readlink sed sha256sum sort ss stat systemctl tr; do
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
        sed 's/pid=//' |
        sort -n -u
}

classify_db_candidate() {
    file=$1
    [ -f "$file" ] || return 0
    if ! grep -Eiq 'DBHOST|database[_ -]*host|mysql[_ -]*host|mariadb[_ -]*host|mysqld\.sock|@mariadb' "$file" 2>/dev/null; then
        return 0
    fi
    echo "db_transport_candidate=$file"
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" 2>&1 || true
    sha256sum "$file" 2>&1 || true
    scopes=""
    grep -Eiq 'localhost|127\.0\.0\.1|::1' "$file" 2>/dev/null && scopes="$scopes loopback"
    grep -Eiq '/run/mysqld/mysqld\.sock|/var/run/mysqld/mysqld\.sock|@mariadb' "$file" 2>/dev/null && scopes="$scopes unix_socket"
    grep -Eiq '10\.77\.' "$file" 2>/dev/null && scopes="$scopes wireguard"
    [ -n "$scopes" ] || scopes=" unresolved"
    echo "db_transport_scopes=$(printf '%s\n' "$scopes" | awk '{$1=$1; print}')"
}

echo "WW.CX MARIADB AND UCP CONSUMER SCOPE AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no database query, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, container, client-address, or traffic change"

section "TARGET LISTENERS"
TARGET_LISTENERS=$(ss -H -ltnpe 2>&1 | grep -E ':(3306|8001|8003)[[:space:]]' || true)
printf '%s\n' "$TARGET_LISTENERS"
for port in 3306 8001 8003; do
    if printf '%s\n' "$TARGET_LISTENERS" | grep -Eq ":${port}[[:space:]]"; then
        echo "port_${port}_listener=present"
    else
        warn "TCP $port listener is absent during the consumer audit"
    fi
done

section "MARIADB SOCKET AND CONFIGURATION TOPOLOGY"
for path in /etc/mysql/my.cnf /etc/mysql/mariadb.cnf; do
    [ -e "$path" ] || continue
    echo "path=$path"
    stat -c 'entry_mode=%a entry_owner=%U entry_group=%G entry_type=%F entry_path=%n' "$path" 2>&1 || true
    target=$(readlink -f "$path" 2>/dev/null || true)
    echo "resolved_target=${target:-unresolved}"
    [ -n "$target" ] && stat -L -c 'target_mode=%a target_owner=%U target_group=%G target_type=%F target_path=%n' "$path" 2>&1 || true
    [ -n "$target" ] && [ -f "$target" ] && sha256sum "$target" 2>&1 || true
done

systemctl show mariadb.socket \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p Listen -p Accept -p Service -p ControlGroup \
    -p Triggers -p TriggeredBy 2>&1 || true
systemctl status mariadb.socket --no-pager --lines=0 2>&1 || true
systemctl cat mariadb.socket 2>&1 | sed -n '1,260p' || true

systemctl show mariadb.service \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p Type -p MainPID -p ControlGroup -p User -p Group \
    -p Requires -p Wants -p After -p Restart 2>&1 || true
systemctl status mariadb.service --no-pager --lines=0 2>&1 || true

section "MARIADB ESTABLISHED CONNECTION SCOPE COUNTS"
ss -Htnp state established 2>/dev/null |
    awk '
    function scope(endpoint) {
        if (endpoint ~ /^127\./ || endpoint ~ /^\[::1\]:/ || endpoint ~ /::ffff:127\./) return "loopback";
        if (endpoint ~ /^10\.77\./ || endpoint ~ /::ffff:10\.77\./) return "wireguard";
        return "other";
    }
    $4 ~ /:3306$/ {
        key = "local_" scope($4) "__peer_" scope($5);
        counts[key]++;
        total++;
    }
    END {
        print "tcp_3306_established_total=" total + 0;
        for (key in counts) print "tcp_3306_scope_" key "=" counts[key];
    }' |
    sort

section "DATABASE TRANSPORT CANDIDATES"
for file in \
    /etc/freepbx.conf \
    /etc/amportal.conf \
    /var/www/html/admin/config.php \
    /var/www/html/admin/bootstrap.php \
    /etc/asterisk/cdr_mysql.conf \
    /etc/asterisk/cel_mysql.conf \
    /etc/asterisk/res_config_mysql.conf \
    /etc/odbc.ini \
    /etc/asterisk/res_odbc.conf; do
    classify_db_candidate "$file"
done

for root in /etc/systemd/system /lib/systemd/system /usr/lib/systemd/system; do
    [ -d "$root" ] || continue
    grep -RlsE --include='*.service' --include='*.socket' --include='*.conf' \
        '(3306|mysqld\.sock|@mariadb)' "$root" 2>/dev/null |
        sed 's/^/db_unit_reference=/' |
        sed -n '1,220p' || true
done

section "UCP LISTENER PROCESS"
UCP_PIDS=""
for port in 8001 8003; do
    pids=$(listener_pids "$port" || true)
    echo "port_${port}_pids=${pids:-none}"
    UCP_PIDS=$(printf '%s\n%s\n' "$UCP_PIDS" "$pids" | awk 'NF' | sort -n -u)
done

UCP_ROOT=""
if [ -n "$UCP_PIDS" ]; then
    for pid in $UCP_PIDS; do
        [ -r "/proc/$pid/comm" ] || { warn "UCP listener PID $pid disappeared"; continue; }
        echo "pid=$pid"
        ps -p "$pid" -o pid=,ppid=,lstart=,etime=,user=,group=,stat=,comm= 2>&1 || true
        exe=$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)
        cgroup=$(awk -F: '$1 == "0" {print $3; exit}' "/proc/$pid/cgroup" 2>/dev/null || true)
        echo "exe=$exe"
        echo "cwd=$cwd"
        echo "process_cgroup=$cgroup"
        case "$exe" in
            */node|*/nodejs)
                case "$cwd" in
                    /var/www/html/admin/modules/ucp/node*) UCP_ROOT=$cwd ;;
                esac
                ;;
        esac
    done
else
    warn "No listener PID was resolved for TCP 8001 or 8003"
fi

echo "ucp_root=${UCP_ROOT:-unresolved}"

section "UCP BIND AND CONSUMER SOURCE REFERENCES"
if [ -n "$UCP_ROOT" ] && [ -d "$UCP_ROOT" ]; then
    for file in "$UCP_ROOT/index.js" "$UCP_ROOT/package.json"; do
        [ -f "$file" ] || continue
        stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" 2>&1 || true
        sha256sum "$file" 2>&1 || true
    done

    find "$UCP_ROOT" -maxdepth 4 -type f \( -name '*.js' -o -name '*.json' \) \
        ! -path '*/node_modules/*' ! -name '.env' -print 2>/dev/null |
        sort |
        while IFS= read -r file; do
            [ -n "$file" ] || continue
            if grep -Eq '8001|8003|listen[[:space:]]*\(|socket\.io|websocket|allowedOrigins|allowRequest|bind-address|bindAddress' "$file" 2>/dev/null; then
                echo "ucp_bind_reference_file=$file"
                grep -nE '8001|8003|listen[[:space:]]*\(|socket\.io|websocket|allowedOrigins|allowRequest|bind-address|bindAddress' "$file" 2>/dev/null |
                    sed -n '1,160p' || true
            fi
        done
else
    warn "UCP source root could not be resolved from the listener process"
fi

for root in \
    /var/www/html/admin/modules/ucp \
    /var/www/html/admin/modules/framework \
    /var/www/html/admin/libraries; do
    [ -d "$root" ] || continue
    grep -RlsE --include='*.php' --include='*.js' --include='*.json' \
        '(^|[^0-9])(8001|8003)([^0-9]|$)' "$root" 2>/dev/null |
        sed 's/^/ucp_consumer_reference=/' |
        sed -n '1,300p' || true
done

section "UCP CONNECTION SCOPE COUNTS"
ss -Htnp state established 2>/dev/null |
    awk '
    function scope(endpoint) {
        if (endpoint ~ /^127\./ || endpoint ~ /^\[::1\]:/ || endpoint ~ /::ffff:127\./) return "loopback";
        if (endpoint ~ /^10\.77\./ || endpoint ~ /::ffff:10\.77\./) return "wireguard";
        return "other";
    }
    $4 ~ /:(8001|8003)$/ {
        port = $4;
        sub(/^.*:/, "", port);
        key = "port_" port "__local_" scope($4) "__peer_" scope($5);
        counts[key]++;
        total[port]++;
    }
    END {
        print "tcp_8001_established_total=" total["8001"] + 0;
        print "tcp_8003_established_total=" total["8003"] + 0;
        for (key in counts) print "ucp_scope_" key "=" counts[key];
    }' |
    sort

section "PM2 FILE METADATA"
for file in /home/asterisk/.pm2/dump.pm2 /home/asterisk/.pm2/pm2.pid; do
    [ -f "$file" ] || continue
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" 2>&1 || true
    sha256sum "$file" 2>&1 || true
done

echo "pm2_environment_read=no"

section "AUTHORITATIVE FIREWALL BOUNDARY"
nft -a list chain inet wwcxfw input 2>&1 || true

section "NARROWING DECISION GATES"
echo "mariadb_gates:"
echo "- classify every established TCP 3306 connection by scope"
echo "- confirm local consumers support loopback or Unix sockets"
echo "- if narrowing, override mariadb.socket as well as preserving Unix socket activation"
echo "- verify /etc/mysql/my.cnf symlink and target permissions before correction"
echo "ucp_gates:"
echo "- identify where FreePBX publishes ports 8001 and 8003 to clients"
echo "- confirm required browser, WebSocket and origin behavior"
echo "- do not infer that zero point-in-time connections means the service is unused"
echo "- choose listener narrowing or an authenticated reverse proxy only after consumer attribution"
echo "shared_boundary:"
echo "- public-interface traffic remains default-dropped"
echo "- broad WireGuard acceptance remains the effective internal exposure path"

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No database query, grant inspection, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, container, or traffic change was performed."
