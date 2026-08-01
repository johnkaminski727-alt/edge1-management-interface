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
            echo "Read-only corrected endpoint and process attribution for MariaDB TCP 3306 and FreePBX UCP TCP 8001/8003."
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

for command in awk date find grep hostname id ps readlink sed sha256sum sort ss stat systemctl; do
    command -v "$command" >/dev/null 2>&1 || { echo "ERROR missing command: $command" >&2; exit 2; }
done

warnings=0
failures=0
warn() { warnings=$((warnings + 1)); echo "WARNING: $*"; }
fail() { failures=$((failures + 1)); echo "FAIL: $*"; }
section() { echo; echo "=== $* ==="; }

sanitize_connections() {
    port_re=$1
    ss -Htnpe state established 2>/dev/null |
        awk -v port_re="$port_re" '
        function scope(endpoint) {
            if (endpoint ~ /^127\./ || endpoint ~ /^\[::1\]:/ || endpoint ~ /::ffff:127\./) return "loopback";
            if (endpoint ~ /^10\.77\./ || endpoint ~ /::ffff:10\.77\./) return "wireguard";
            if (endpoint ~ /^89\.147\.109\.253:/ || endpoint ~ /::ffff:89\.147\.109\.253/) return "public_interface";
            return "other";
        }
        function first_pid(line, token) {
            if (match(line, /pid=[0-9]+/)) {
                token = substr(line, RSTART + 4, RLENGTH - 4);
                return token;
            }
            return "none";
        }
        function first_name(line, token) {
            if (match(line, /users:\(\(\"[^\"]+\"/)) {
                token = substr(line, RSTART, RLENGTH);
                sub(/^users:\(\(\"/, "", token);
                sub(/\"$/, "", token);
                return token;
            }
            return "unknown";
        }
        $3 ~ port_re || $4 ~ port_re {
            n++;
            direction = "unresolved";
            if ($3 ~ port_re && $4 ~ port_re) direction = "both_endpoints_target_port";
            else if ($3 ~ port_re) direction = "local_service_endpoint";
            else if ($4 ~ port_re) direction = "local_client_to_service";
            print "connection_" n "_direction=" direction;
            print "connection_" n "_local_scope=" scope($3);
            print "connection_" n "_peer_scope=" scope($4);
            print "connection_" n "_process_name=" first_name($0);
            print "connection_" n "_process_pid=" first_pid($0);
            directions[direction]++;
            local_scopes[scope($3)]++;
            peer_scopes[scope($4)]++;
        }
        END {
            print "connection_total=" n + 0;
            for (key in directions) print "direction_count_" key "=" directions[key];
            for (key in local_scopes) print "local_scope_count_" key "=" local_scopes[key];
            for (key in peer_scopes) print "peer_scope_count_" key "=" peer_scopes[key];
        }' |
        sort
}

connection_pids() {
    port_re=$1
    ss -Htnpe state established 2>/dev/null |
        awk -v port_re="$port_re" '$3 ~ port_re || $4 ~ port_re' |
        grep -oE 'pid=[0-9]+' |
        sed 's/pid=//' |
        sort -n -u
}

report_pid() {
    pid=$1
    [ -r "/proc/$pid/comm" ] || { warn "Connection PID $pid disappeared"; return 0; }
    echo "pid=$pid"
    ps -p "$pid" -o pid=,ppid=,lstart=,etime=,user=,group=,stat=,comm= 2>&1 || true
    echo "exe=$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
    echo "cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    echo "process_cgroup=$(awk -F: '$1 == "0" {print $3; exit}' "/proc/$pid/cgroup" 2>/dev/null || true)"
}

echo "WW.CX MARIADB AND UCP ENDPOINT ATTRIBUTION AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; endpoint addresses are reduced to scope labels; no database query, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, packet capture, external scan, or traffic change"

section "CORRECTED MARIADB TCP 3306 ENDPOINT CLASSIFICATION"
sanitize_connections '(:3306)$'
DB_PIDS=$(connection_pids '(:3306)$' || true)
echo "mariadb_connection_pids=${DB_PIDS:-none}"
for pid in $DB_PIDS; do
    report_pid "$pid"
done

section "MARIADB LISTENER AND TRANSPORT CONTRACT"
ss -H -ltnpe 2>/dev/null | grep -E ':3306[[:space:]]' || warn "TCP 3306 listener is absent"
systemctl show mariadb.socket -p Id -p ActiveState -p SubState -p UnitFileState -p FragmentPath -p Listen -p Accept -p ControlGroup 2>&1 || true
systemctl show mariadb.service -p Id -p ActiveState -p SubState -p MainPID -p ControlGroup -p User -p Group 2>&1 || true
for file in /etc/freepbx.conf /etc/amportal.conf /etc/asterisk/res_config_mysql.conf /etc/odbc.ini /etc/asterisk/res_odbc.conf; do
    [ -f "$file" ] || continue
    echo "transport_file=$file"
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" 2>&1 || true
    sha256sum "$file" 2>&1 || true
    scopes=""
    grep -Eiq 'localhost|127\.0\.0\.1|::1' "$file" 2>/dev/null && scopes="$scopes loopback"
    grep -Eiq '/run/mysqld/mysqld\.sock|/var/run/mysqld/mysqld\.sock|@mariadb' "$file" 2>/dev/null && scopes="$scopes unix_socket"
    grep -Eiq '10\.77\.' "$file" 2>/dev/null && scopes="$scopes wireguard"
    [ -n "$scopes" ] || scopes=" unresolved"
    echo "transport_scopes=$(printf '%s\n' "$scopes" | awk '{$1=$1; print}')"
done

section "CORRECTED UCP ENDPOINT CLASSIFICATION"
sanitize_connections ':(8001|8003)$'
UCP_CONN_PIDS=$(connection_pids ':(8001|8003)$' || true)
echo "ucp_connection_pids=${UCP_CONN_PIDS:-none}"
for pid in $UCP_CONN_PIDS; do
    report_pid "$pid"
done

section "UCP BIND POLICY SOURCE"
UCP_SERVER=/var/www/html/admin/modules/ucp/node/lib/server.js
if [ -f "$UCP_SERVER" ]; then
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$UCP_SERVER" 2>&1 || true
    sha256sum "$UCP_SERVER" 2>&1 || true
    grep -nE '(^|[^A-Za-z])(hostS?|portS?)[[:space:]]*=|serverS?\.listen|process\.argv|process\.env|socket\.io|allowedOrigins|allowRequest|cors' "$UCP_SERVER" 2>/dev/null |
        sed -n '1,220p' || true
else
    fail "$UCP_SERVER is missing"
fi

section "UCP CLIENT PUBLICATION REFERENCES"
for root in /var/www/html/admin/modules/ucp/htdocs /var/www/html/admin/modules/ucp; do
    [ -d "$root" ] || continue
    find "$root" -type f \( -name '*.php' -o -name '*.js' -o -name '*.json' \) \
        ! -path '*/vendor/*' ! -path '*/node_modules/*' ! -name '.env' -print 2>/dev/null |
        sort |
        while IFS= read -r file; do
            [ -n "$file" ] || continue
            if grep -Eq '8001|8003|socket\.io|WebSocket|websocket|ws://|wss://|hostS?|portS?|UCPNODE' "$file" 2>/dev/null; then
                echo "publication_reference_file=$file"
                grep -nE '8001|8003|socket\.io|WebSocket|websocket|ws://|wss://|hostS?|portS?|UCPNODE' "$file" 2>/dev/null |
                    sed -n '1,180p' || true
            fi
        done
done

section "DECISION GATES"
echo "mariadb:"
echo "- accept loopback-only or Unix-socket narrowing only if every corrected connection row is local and every identified consumer supports the retained transport"
echo "- a systemd socket override must preserve @mariadb and /run/mysqld/mysqld.sock"
echo "- activation requires daemon-reload plus controlled MariaDB socket/service restart and rollback evidence"
echo "ucp:"
echo "- bind narrowing requires exact host defaults and client publication behavior"
echo "- an authenticated HTTPS/WebSocket reverse proxy is preferred if browsers require remote UCP access"
echo "- zero current connections is not a disablement decision"

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No database query, grant inspection, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, packet capture, external scan, container, or traffic change was performed."
