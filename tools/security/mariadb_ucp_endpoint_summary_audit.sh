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
            echo "Compact read-only endpoint and process summary for MariaDB and FreePBX UCP."
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

for command in awk date grep hostname id ps readlink sed sort ss; do
    command -v "$command" >/dev/null 2>&1 || { echo "ERROR missing command: $command" >&2; exit 2; }
done

warnings=0
failures=0
warn() { warnings=$((warnings + 1)); echo "WARNING: $*"; }
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

summarize_listener() {
    port=$1
    ss -H -ltnpe 2>/dev/null |
        awk -v port="$port" '
        function scope(endpoint) {
            if (endpoint ~ /^127\./ || endpoint ~ /^\[::1\]:/) return "loopback";
            if (endpoint ~ /^10\.77\./) return "wireguard";
            if (endpoint ~ /^89\.147\.109\.253:/) return "public_interface";
            if (endpoint ~ /^\*:/ || endpoint ~ /^0\.0\.0\.0:/ || endpoint ~ /^\[::\]:/) return "wildcard";
            return "other";
        }
        $4 ~ (":" port "$") {
            n++;
            print "listener_" n "_scope=" scope($4);
            if (match($0, /pid=[0-9]+/)) print "listener_" n "_pid=" substr($0, RSTART + 4, RLENGTH - 4);
        }
        END { print "listener_total=" n + 0; }' |
        sort
}

echo "WW.CX MARIADB AND UCP ENDPOINT SUMMARY AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: compact read-only summary; endpoint addresses are reduced to scope labels; no database query, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, packet capture, external scan, or traffic change"

section "MARIADB TCP 3306 CONNECTIONS"
sanitize_connections '(:3306)$'
DB_PIDS=$(connection_pids '(:3306)$' || true)
echo "mariadb_connection_pids=${DB_PIDS:-none}"
for pid in $DB_PIDS; do report_pid "$pid"; done

section "MARIADB TCP 3306 LISTENER"
summarize_listener 3306

section "UCP TCP 8001 CONNECTIONS"
sanitize_connections '(:8001)$'
UCP_8001_PIDS=$(connection_pids '(:8001)$' || true)
echo "ucp_8001_connection_pids=${UCP_8001_PIDS:-none}"
for pid in $UCP_8001_PIDS; do report_pid "$pid"; done

section "UCP TCP 8003 CONNECTIONS"
sanitize_connections '(:8003)$'
UCP_8003_PIDS=$(connection_pids '(:8003)$' || true)
echo "ucp_8003_connection_pids=${UCP_8003_PIDS:-none}"
for pid in $UCP_8003_PIDS; do report_pid "$pid"; done

section "UCP LISTENERS"
echo "port=8001"
summarize_listener 8001
echo "port=8003"
summarize_listener 8003

section "UCP BIND AND PUBLICATION CONTRACT"
SERVER=/var/www/html/admin/modules/ucp/node/lib/server.js
SETTINGS=/var/www/html/admin/modules/ucp/Ucp.class.php
PUBLICATION=/var/www/html/admin/modules/ucp/htdocs/includes/UCP.class.php
BROWSER=/var/www/html/admin/modules/ucp/htdocs/assets/js/ucp.js

[ -f "$SERVER" ] && grep -nE 'port = 8001|host = "0\.0\.0\.0"|portS = 8003|hostS = "0\.0\.0\.0"|NODEJSBINDADDRESS|NODEJSBINDPORT|NODEJSHTTPSBINDADDRESS|NODEJSHTTPSBINDPORT|server\.listen|serverS\.listen' "$SERVER" 2>/dev/null || warn "$SERVER is unavailable"
[ -f "$SETTINGS" ] && grep -nE 'NODEJSENABLED|NODEJSTLSENABLED|NODEJSBINDADDRESS|NODEJSBINDPORT|NODEJSHTTPSBINDADDRESS|NODEJSHTTPSBINDPORT' "$SETTINGS" 2>/dev/null | sed -n '1,100p' || warn "$SETTINGS is unavailable"
[ -f "$PUBLICATION" ] && grep -nE 'NODEJSBINDPORT|NODEJSHTTPSBINDPORT|HTTP_HOST|return \[ "enabled"' "$PUBLICATION" 2>/dev/null | sed -n '1,100p' || warn "$PUBLICATION is unavailable"
[ -f "$BROWSER" ] && grep -nE 'ucpserver\.host|ucpserver\.port|ucpserver\.portS|connectString = .*wss?://' "$BROWSER" 2>/dev/null | sed -n '1,100p' || warn "$BROWSER is unavailable"

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No database query, grant inspection, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, packet capture, external scan, container, or traffic change was performed."
