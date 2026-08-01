#!/bin/sh
set -eu
umask 077

EXPECTED_HOST="edge1.ww.cx"
EVIDENCE_DIR=""
APPLY=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --expected-host)
            [ "$#" -ge 2 ] || { echo "ERROR missing hostname" >&2; exit 2; }
            EXPECTED_HOST=$2
            shift 2
            ;;
        --evidence-dir)
            [ "$#" -ge 2 ] || { echo "ERROR missing evidence directory" >&2; exit 2; }
            EVIDENCE_DIR=$2
            shift 2
            ;;
        --apply)
            APPLY=1
            shift
            ;;
        -h|--help)
            echo "Usage: sudo EDGE1_ALLOW_CONDITIONAL=1 $0 --apply --evidence-dir DIR [--expected-host HOST]"
            echo "Atomically install, verify, and automatically roll back the approved MariaDB loopback-only socket drop-in."
            exit 0
            ;;
        *)
            echo "ERROR unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR run as root through sudo" >&2; exit 2; }
[ "$APPLY" -eq 1 ] || { echo "ERROR --apply is required" >&2; exit 2; }
[ "${EDGE1_ALLOW_CONDITIONAL:-0}" = "1" ] || {
    echo "ERROR EDGE1_ALLOW_CONDITIONAL=1 is required for this conditional production change" >&2
    exit 2
}
[ -n "$EVIDENCE_DIR" ] || { echo "ERROR --evidence-dir is required" >&2; exit 2; }
case "$EVIDENCE_DIR" in
    /var/lib/wwcx-deployment-evidence/mariadb-loopback-hardening/*) ;;
    *)
        echo "ERROR evidence directory must be below /var/lib/wwcx-deployment-evidence/mariadb-loopback-hardening" >&2
        exit 2
        ;;
esac

HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || { echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2; exit 2; }

for command in asterisk awk chmod cp date dirname find grep hostname id install journalctl mkdir readlink rm sha256sum sleep sort ss stat systemctl systemd-analyze xargs; do
    command -v "$command" >/dev/null 2>&1 || { echo "ERROR missing command: $command" >&2; exit 2; }
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
SOURCE="$REPO_ROOT/templates/systemd/mariadb.socket.d/10-loopback-only.conf"
PREFLIGHT="$REPO_ROOT/tools/security/mariadb_loopback_socket_preflight_audit.sh"
ODBC_GATE="$REPO_ROOT/tools/security/asterisk_res_odbc_path_audit.sh"
DROPIN_DIR=/etc/systemd/system/mariadb.socket.d
DROPIN="$DROPIN_DIR/10-loopback-only.conf"
EXPECTED_SOURCE_SHA=c5365e2d9bd882fcf62a8676b98f8f996094c5b5e45572fe9a0244b7f4f32fea
POST_CHANGE_ATTEMPTS=60
ROLLBACK_ARMED=0

mkdir -p "$EVIDENCE_DIR"
chmod 0700 "$EVIDENCE_DIR"

log() {
    printf '%s\n' "$*"
}

hash_file() {
    file=$1
    [ -f "$file" ] && sha256sum "$file" || true
}

verify_units() {
    output=$1
    shift
    systemd-analyze verify --man=no "$@" >"$output" 2>&1
}

capture_before() {
    systemctl show mariadb.socket mariadb.service >"$EVIDENCE_DIR/systemd-before.txt" 2>&1
    ss -H -ltnpe >"$EVIDENCE_DIR/tcp-listeners-before.txt" 2>&1
    ss -H -lxnp >"$EVIDENCE_DIR/unix-listeners-before.txt" 2>&1
    asterisk -rx 'core show uptime' >"$EVIDENCE_DIR/asterisk-uptime-before.txt" 2>&1
    asterisk -rx 'core show channels count' >"$EVIDENCE_DIR/asterisk-channels-before.txt" 2>&1
}

zero_call_gate() {
    channels_file=$1
    grep -Eq '0 active channels' "$channels_file" && grep -Eq '0 active calls' "$channels_file"
}

restore_previous_dropin() {
    if [ -f "$EVIDENCE_DIR/10-loopback-only.conf.before" ]; then
        install -d -m 0755 -o root -g root "$DROPIN_DIR"
        install -m 0644 -o root -g root \
            "$EVIDENCE_DIR/10-loopback-only.conf.before" "$DROPIN"
    elif [ -f "$EVIDENCE_DIR/dropin-was-absent" ]; then
        rm -f "$DROPIN"
    else
        log "ROLLBACK ERROR: prior drop-in state marker is missing"
        return 1
    fi
}

restart_mariadb_pair() {
    systemctl stop mariadb.service mariadb.socket >/dev/null 2>&1 || true
    systemctl start mariadb.socket
    systemctl start mariadb.service
    systemctl is-active --quiet mariadb.socket
    systemctl is-active --quiet mariadb.service
}

rollback() {
    log "ROLLBACK: restoring the prior MariaDB socket contract"
    systemctl stop mariadb.service mariadb.socket >/dev/null 2>&1 || true
    restore_previous_dropin || return 1
    systemctl daemon-reload || return 1

    verify_rc=0
    verify_units "$EVIDENCE_DIR/systemd-verify-rollback.txt" mariadb.socket mariadb.service || verify_rc=$?

    restart_mariadb_pair || return 1
    wait_for_ucp_runtime "$EVIDENCE_DIR/tcp-listeners-after-rollback.txt" || return 1
    systemctl show mariadb.socket mariadb.service \
        >"$EVIDENCE_DIR/systemd-after-rollback.txt" 2>&1 || true
    ss -H -lxnp >"$EVIDENCE_DIR/unix-listeners-after-rollback.txt" 2>&1 || true
    ss -Htnpe state established \
        >"$EVIDENCE_DIR/mariadb-connections-after-rollback.txt" 2>&1 || true
    journalctl -u mariadb.socket -u mariadb.service -u freepbx.service \
        --since '-10 minutes' --no-pager \
        >"$EVIDENCE_DIR/journal-after-rollback.txt" 2>&1 || true

    if [ "$verify_rc" -ne 0 ]; then
        log "ROLLBACK WARNING: static systemd verification failed after restoring the prior contract; the MariaDB socket and service were nevertheless restarted and verified active"
    fi
    log "ROLLBACK COMPLETE"
}

fail_after_mutation() {
    message=$1
    log "FAIL: $message"
    if [ "$ROLLBACK_ARMED" -eq 1 ]; then
        if rollback; then
            log "Audit state: CHANGE FAILED AND ROLLED BACK"
            exit 1
        fi
        log "CRITICAL: automatic rollback failed; preserve this shell and inspect evidence immediately"
        exit 2
    fi
    exit 1
}

listener_contract_ok() {
    listeners=$1
    grep -Eq '127\.0\.0\.1:3306[[:space:]]' "$listeners" || return 1
    grep -Eq '\[::1\]:3306[[:space:]]' "$listeners" || return 1
    if grep -Eq '(^|[[:space:]])(\*:3306|0\.0\.0\.0:3306|\[::\]:3306)[[:space:]]' "$listeners"; then
        return 1
    fi
    return 0
}

unix_contract_ok() {
    listeners=$1
    grep -Fq '/run/mysqld/mysqld.sock' "$listeners" && grep -Fq '@mariadb' "$listeners"
}

ucp_contract_ok() {
    listeners=$1
    grep -Eq ':8001[[:space:]]' "$listeners" && grep -Eq ':8003[[:space:]]' "$listeners"
}

ucp_loopback_connection_reestablished() {
    ss -Htnpe state established 2>/dev/null |
        awk '
        function loopback(endpoint) {
            return endpoint ~ /^127\./ || endpoint ~ /^\[::1\]:/ || endpoint ~ /::ffff:127\./;
        }
        $3 ~ /:3306$/ || $4 ~ /:3306$/ {
            found++;
            if (!loopback($3) || !loopback($4)) bad++;
            if ($4 ~ /:3306$/ && loopback($3) && loopback($4) && $0 ~ /users:\(\(\"node/) ucp_client++;
        }
        END { exit !(found > 0 && bad == 0 && ucp_client > 0); }
        '
}

wait_for_ucp_runtime() {
    tcp_output=$1
    attempt=1
    while [ "$attempt" -le "$POST_CHANGE_ATTEMPTS" ]; do
        ss -H -ltnpe >"$tcp_output" 2>&1 || return 1
        if ucp_contract_ok "$tcp_output" && ucp_loopback_connection_reestablished; then
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    return 1
}

wait_for_post_change_runtime() {
    attempt=1
    while [ "$attempt" -le "$POST_CHANGE_ATTEMPTS" ]; do
        ss -H -ltnpe >"$EVIDENCE_DIR/tcp-listeners-after.txt" 2>&1 || return 1
        ss -H -lxnp >"$EVIDENCE_DIR/unix-listeners-after.txt" 2>&1 || return 1
        if listener_contract_ok "$EVIDENCE_DIR/tcp-listeners-after.txt" && \
           unix_contract_ok "$EVIDENCE_DIR/unix-listeners-after.txt" && \
           ucp_contract_ok "$EVIDENCE_DIR/tcp-listeners-after.txt" && \
           ucp_loopback_connection_reestablished; then
            printf '%s\n' "$attempt" >"$EVIDENCE_DIR/post-change-readiness-attempts.txt"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    printf '%s\n' "$POST_CHANGE_ATTEMPTS" >"$EVIDENCE_DIR/post-change-readiness-attempts.txt"
    return 1
}

log "WW.CX MARIADB LOOPBACK SOCKET HARDENING"
log "Host: $HOST"
log "Time: $(date -Is)"
log "Mode: conditional atomic change with automatic rollback; UCP, FreePBX, Asterisk, firewall, WireGuard, database contents, grants, schemas, packages, calls, CAP feeds and external traffic are not modified"

cd "$REPO_ROOT"

[ -f "$SOURCE" ] || { log "FAIL: candidate source is missing"; exit 1; }
SOURCE_SHA=$(sha256sum "$SOURCE" | awk '{print $1}')
[ "$SOURCE_SHA" = "$EXPECTED_SOURCE_SHA" ] || {
    log "FAIL: candidate SHA-256 differs from the approved contract"
    exit 1
}
printf '%s  %s\n' "$SOURCE_SHA" "$SOURCE" >"$EVIDENCE_DIR/source.sha256"

log "Running final read-only gates"
sh "$PREFLIGHT" --expected-host "$EXPECTED_HOST" \
    >"$EVIDENCE_DIR/mariadb-preflight.txt" 2>&1 || {
        log "FAIL: MariaDB preflight did not pass"
        exit 1
    }
sha256sum "$EVIDENCE_DIR/mariadb-preflight.txt" >"$EVIDENCE_DIR/mariadb-preflight.txt.sha256"

sh "$ODBC_GATE" --expected-host "$EXPECTED_HOST" \
    >"$EVIDENCE_DIR/res-odbc-path-gate.txt" 2>&1 || {
        log "FAIL: res_odbc path gate did not pass"
        exit 1
    }
sha256sum "$EVIDENCE_DIR/res-odbc-path-gate.txt" >"$EVIDENCE_DIR/res-odbc-path-gate.txt.sha256"

capture_before
zero_call_gate "$EVIDENCE_DIR/asterisk-channels-before.txt" || {
    log "FAIL: active Asterisk channels or calls are present; change not started"
    exit 1
}

if [ -e "$DROPIN" ]; then
    cp -a "$DROPIN" "$EVIDENCE_DIR/10-loopback-only.conf.before"
    hash_file "$DROPIN" >"$EVIDENCE_DIR/dropin-before.sha256"
else
    : >"$EVIDENCE_DIR/dropin-was-absent"
fi
ROLLBACK_ARMED=1

log "Installing approved systemd socket drop-in"
install -d -m 0755 -o root -g root "$DROPIN_DIR" || fail_after_mutation "could not create drop-in directory"
install -m 0644 -o root -g root "$SOURCE" "$DROPIN" || fail_after_mutation "could not install drop-in"
sha256sum "$DROPIN" >"$EVIDENCE_DIR/dropin-installed.sha256" || fail_after_mutation "could not hash installed drop-in"

systemctl daemon-reload || fail_after_mutation "systemd daemon-reload failed"
verify_units "$EVIDENCE_DIR/systemd-verify-installed.txt" mariadb.socket mariadb.service || fail_after_mutation "systemd verification failed"

log "Restarting MariaDB socket and service as one bounded maintenance action"
restart_mariadb_pair || fail_after_mutation "MariaDB socket/service restart failed"

systemctl show mariadb.socket mariadb.service >"$EVIDENCE_DIR/systemd-after.txt" 2>&1 || fail_after_mutation "could not capture post-change systemd state"

log "Waiting up to $POST_CHANGE_ATTEMPTS seconds for MariaDB and FreePBX/UCP readiness"
if ! wait_for_post_change_runtime; then
    listener_contract_ok "$EVIDENCE_DIR/tcp-listeners-after.txt" || fail_after_mutation "TCP 3306 does not match IPv4/IPv6 loopback-only contract"
    unix_contract_ok "$EVIDENCE_DIR/unix-listeners-after.txt" || fail_after_mutation "required MariaDB Unix sockets are missing"
    ucp_contract_ok "$EVIDENCE_DIR/tcp-listeners-after.txt" || fail_after_mutation "UCP listeners did not recover within the readiness window"
    ucp_loopback_connection_reestablished || fail_after_mutation "the local UCP Node MariaDB TCP relationship did not recover within the readiness window"
    fail_after_mutation "post-change MariaDB/UCP readiness timed out"
fi
log "Post-change MariaDB and UCP readiness gate passed"

ss -Htnpe state established 2>/dev/null |
    awk '
    function scope(endpoint) {
        if (endpoint ~ /^127\./ || endpoint ~ /^\[::1\]:/ || endpoint ~ /::ffff:127\./) return "loopback";
        return "other";
    }
    $3 ~ /:3306$/ || $4 ~ /:3306$/ {
        n++;
        print "connection_" n "_local_scope=" scope($3);
        print "connection_" n "_peer_scope=" scope($4);
    }
    END { print "connection_total=" n + 0; }
    ' >"$EVIDENCE_DIR/mariadb-connections-after.txt"

after_channels="$EVIDENCE_DIR/asterisk-channels-after.txt"
asterisk -rx 'core show uptime' >"$EVIDENCE_DIR/asterisk-uptime-after.txt" 2>&1 || fail_after_mutation "Asterisk uptime check failed"
asterisk -rx 'core show channels count' >"$after_channels" 2>&1 || fail_after_mutation "Asterisk channel check failed"

journalctl -u mariadb.socket -u mariadb.service -u freepbx.service \
    --since '-10 minutes' --no-pager \
    >"$EVIDENCE_DIR/journal-after.txt" 2>&1 || true

find "$EVIDENCE_DIR" -maxdepth 1 -type f ! -name 'evidence-files.sha256' -print0 2>/dev/null |
    sort -z |
    xargs -0 sha256sum >"$EVIDENCE_DIR/evidence-files.sha256" 2>/dev/null || true

ROLLBACK_ARMED=0
log "Audit state: CHANGE APPLIED AND VERIFIED"
log "MariaDB TCP 3306 is loopback-only; both Unix sockets remain present; UCP 8001/8003 remain unchanged."
log "Evidence directory: $EVIDENCE_DIR"
