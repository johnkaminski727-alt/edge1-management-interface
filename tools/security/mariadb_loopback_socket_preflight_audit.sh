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
            echo "Read-only preflight for the MariaDB loopback-only socket candidate."
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

for command in awk date grep hostname id ps readlink sed sha256sum sort ss stat systemctl; do
    command -v "$command" >/dev/null 2>&1 || { echo "ERROR missing command: $command" >&2; exit 2; }
done

warnings=0
failures=0
warn() { warnings=$((warnings + 1)); echo "WARNING: $*"; }
fail() { failures=$((failures + 1)); echo "FAIL: $*"; }
section() { echo; echo "=== $* ==="; }

scope_connections() {
    ss -Htnpe state established 2>/dev/null |
        awk '
        function scope(endpoint) {
            if (endpoint ~ /^127\./ || endpoint ~ /^\[::1\]:/ || endpoint ~ /::ffff:127\./) return "loopback";
            if (endpoint ~ /^10\.77\./ || endpoint ~ /::ffff:10\.77\./) return "wireguard";
            if (endpoint ~ /^89\.147\.109\.253:/ || endpoint ~ /::ffff:89\.147\.109\.253/) return "public_interface";
            return "other";
        }
        function first_pid(line, token) {
            if (match(line, /pid=[0-9]+/)) return substr(line, RSTART + 4, RLENGTH - 4);
            return "none";
        }
        function first_name(line, token) {
            token = line;
            sub(/^.*users:\(\(/, "", token);
            if (token == line) return "unknown";
            sub(/^"/, "", token);
            sub(/".*$/, "", token);
            return token;
        }
        $3 ~ /:3306$/ || $4 ~ /:3306$/ {
            n++;
            direction = "unresolved";
            if ($3 ~ /:3306$/ && $4 ~ /:3306$/) direction = "both_endpoints_target_port";
            else if ($3 ~ /:3306$/) direction = "local_service_endpoint";
            else if ($4 ~ /:3306$/) direction = "local_client_to_service";
            local_scope = scope($3);
            peer_scope = scope($4);
            print "connection_" n "_direction=" direction;
            print "connection_" n "_local_scope=" local_scope;
            print "connection_" n "_peer_scope=" peer_scope;
            print "connection_" n "_process_name=" first_name($0);
            print "connection_" n "_process_pid=" first_pid($0);
            if (local_scope != "loopback" || peer_scope != "loopback") non_loopback++;
        }
        END {
            print "connection_total=" n + 0;
            print "non_loopback_count=" non_loopback + 0;
        }' |
        sort
}

connection_pids() {
    ss -Htnpe state established 2>/dev/null |
        awk '$3 ~ /:3306$/ || $4 ~ /:3306$/' |
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

classify_transport_file() {
    file=$1
    [ -f "$file" ] || return 0
    echo "transport_file=$file"
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" 2>&1 || true
    sha256sum "$file" 2>&1 || true
    scopes=""
    grep -Eiq 'localhost|127\.0\.0\.1|::1' "$file" 2>/dev/null && scopes="$scopes loopback"
    grep -Eiq '/run/mysqld/mysqld\.sock|/var/run/mysqld/mysqld\.sock|@mariadb' "$file" 2>/dev/null && scopes="$scopes unix_socket"
    grep -Eiq '10\.77\.' "$file" 2>/dev/null && scopes="$scopes wireguard"
    [ -n "$scopes" ] || scopes=" unresolved"
    echo "transport_scopes=$(printf '%s\n' "$scopes" | awk '{$1=$1; print}')"
}

CANDIDATE="templates/systemd/mariadb.socket.d/10-loopback-only.conf"

echo "WW.CX MARIADB LOOPBACK SOCKET HARDENING PREFLIGHT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no database query, service, socket, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, packet-capture, external-scan, or traffic change"

section "CANDIDATE CONTRACT"
if [ ! -f "$CANDIDATE" ]; then
    fail "Candidate file is missing: $CANDIDATE"
else
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$CANDIDATE" 2>&1 || true
    sha256sum "$CANDIDATE" 2>&1 || true
    sed -n '1,120p' "$CANDIDATE"
    for required in \
        'ListenStream=' \
        'ListenStream=@mariadb' \
        'ListenStream=/run/mysqld/mysqld.sock' \
        'ListenStream=127.0.0.1:3306' \
        'ListenStream=[::1]:3306'; do
        grep -Fqx "$required" "$CANDIDATE" || fail "Candidate is missing: $required"
    done
fi

section "CURRENT SYSTEMD CONTRACT"
systemctl show mariadb.socket \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p Listen -p Accept -p ControlGroup -p Triggers 2>&1 || true
systemctl show mariadb.service \
    -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p Type -p MainPID -p ControlGroup -p User -p Group -p Restart 2>&1 || true

section "CURRENT TCP AND UNIX LISTENERS"
ss -H -ltnpe 2>/dev/null | grep -E ':3306[[:space:]]' || fail "TCP 3306 listener is absent"
ss -H -lxnp 2>/dev/null | grep -E '(@mariadb|/run/mysqld/mysqld.sock)' || fail "Expected MariaDB Unix sockets are absent"

section "CORRECTED CONNECTION SCOPE"
CONNECTION_SUMMARY=$(scope_connections || true)
printf '%s\n' "$CONNECTION_SUMMARY"
if ! printf '%s\n' "$CONNECTION_SUMMARY" | grep -Fqx 'non_loopback_count=0'; then
    fail "At least one MariaDB TCP connection is not fully loopback scoped"
fi
if printf '%s\n' "$CONNECTION_SUMMARY" | grep -Fqx 'connection_total=0'; then
    warn "No established MariaDB TCP connection was present during preflight"
fi

DB_PIDS=$(connection_pids || true)
echo "mariadb_connection_pids=${DB_PIDS:-none}"
for pid in $DB_PIDS; do report_pid "$pid"; done

section "TRANSPORT CANDIDATES"
for file in \
    /etc/freepbx.conf \
    /etc/amportal.conf \
    /etc/asterisk/res_config_mysql.conf \
    /etc/odbc.ini \
    /etc/asterisk/res_odbc.conf; do
    classify_transport_file "$file"
done

section "FREEPBX UCP BOUNDARY"
ss -H -ltnpe 2>/dev/null | grep -E ':(8001|8003)[[:space:]]' || warn "UCP listeners 8001/8003 were not both observed"
echo "ucp_change_authorized=no"
echo "ucp_reason=direct_browser_websocket_publication_requires_separate_proxy_design"

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY PREFLIGHT PASSED"
echo "No database query, service, socket, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, packet-capture, external-scan, container, or traffic change was performed."
