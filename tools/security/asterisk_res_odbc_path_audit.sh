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
            echo "Read-only file-type and effective-permission audit for /etc/asterisk/res_odbc.conf."
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

for command in awk date hostname id readlink sha256sum stat; do
    command -v "$command" >/dev/null 2>&1 || { echo "ERROR missing command: $command" >&2; exit 2; }
done

warnings=0
failures=0
warn() { warnings=$((warnings + 1)); echo "WARNING: $*"; }
fail() { failures=$((failures + 1)); echo "FAIL: $*"; }

is_group_or_world_writable() {
    mode=$1
    awk -v mode="$mode" '
        function writable(digit) {
            return digit == 2 || digit == 3 || digit == 6 || digit == 7;
        }
        BEGIN {
            group_digit = int((mode + 0) / 10) % 10;
            other_digit = (mode + 0) % 10;
            exit !(writable(group_digit) || writable(other_digit));
        }
    '
}

PATH_TO_CHECK=/etc/asterisk/res_odbc.conf

echo "WW.CX ASTERISK RES_ODBC PATH AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no configuration contents, credential, database query, service, process, listener, firewall, package, ownership, permission, or traffic change"

echo
echo "=== ENTRY ==="
if [ ! -e "$PATH_TO_CHECK" ] && [ ! -L "$PATH_TO_CHECK" ]; then
    fail "$PATH_TO_CHECK is absent"
else
    entry_mode=$(stat -c '%a' "$PATH_TO_CHECK" 2>/dev/null || true)
    entry_owner=$(stat -c '%U' "$PATH_TO_CHECK" 2>/dev/null || true)
    entry_group=$(stat -c '%G' "$PATH_TO_CHECK" 2>/dev/null || true)
    entry_type=$(stat -c '%F' "$PATH_TO_CHECK" 2>/dev/null || true)
    entry_bytes=$(stat -c '%s' "$PATH_TO_CHECK" 2>/dev/null || true)
    echo "entry_path=$PATH_TO_CHECK"
    echo "entry_type=${entry_type:-unresolved}"
    echo "entry_mode=${entry_mode:-unresolved}"
    echo "entry_owner=${entry_owner:-unresolved}"
    echo "entry_group=${entry_group:-unresolved}"
    echo "entry_bytes=${entry_bytes:-unresolved}"

    case "$entry_type" in
        "symbolic link")
            link_target=$(readlink "$PATH_TO_CHECK" 2>/dev/null || true)
            echo "link_target=${link_target:-unresolved}"
            ;;
        "regular file")
            echo "link_target=not_applicable"
            ;;
        *)
            fail "Unexpected entry type: ${entry_type:-unresolved}"
            ;;
    esac
fi

echo
echo "=== EFFECTIVE TARGET ==="
resolved_target=$(readlink -f "$PATH_TO_CHECK" 2>/dev/null || true)
echo "resolved_target=${resolved_target:-unresolved}"
if [ -z "$resolved_target" ] || [ ! -f "$resolved_target" ]; then
    fail "Effective target is not a readable regular file"
else
    target_mode=$(stat -Lc '%a' "$PATH_TO_CHECK" 2>/dev/null || true)
    target_owner=$(stat -Lc '%U' "$PATH_TO_CHECK" 2>/dev/null || true)
    target_group=$(stat -Lc '%G' "$PATH_TO_CHECK" 2>/dev/null || true)
    target_type=$(stat -Lc '%F' "$PATH_TO_CHECK" 2>/dev/null || true)
    target_bytes=$(stat -Lc '%s' "$PATH_TO_CHECK" 2>/dev/null || true)
    echo "target_type=${target_type:-unresolved}"
    echo "target_mode=${target_mode:-unresolved}"
    echo "target_owner=${target_owner:-unresolved}"
    echo "target_group=${target_group:-unresolved}"
    echo "target_bytes=${target_bytes:-unresolved}"
    sha256sum "$resolved_target" 2>&1 || fail "Could not hash effective target"

    if [ "$target_type" != "regular file" ]; then
        fail "Effective target is not a regular file"
    fi
    if [ -n "$target_mode" ] && is_group_or_world_writable "$target_mode"; then
        fail "Effective target is group- or world-writable"
    fi
    if [ "$target_owner" != "root" ] && [ "$target_owner" != "asterisk" ]; then
        warn "Effective target owner is neither root nor asterisk"
    fi
fi

echo
echo "=== PACKAGE ATTRIBUTION ==="
if command -v dpkg-query >/dev/null 2>&1 && [ -n "$resolved_target" ]; then
    package_owner=$(dpkg-query -S "$resolved_target" 2>/dev/null || true)
    if [ -n "$package_owner" ]; then
        echo "package_owner=$package_owner"
    else
        echo "package_owner=not_attributed"
    fi
else
    echo "package_owner=unavailable"
fi

echo
echo "=== RESULT ==="
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi
echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No configuration contents, credential, database query, service, process, listener, firewall, package, ownership, permission, logger, or traffic change was performed."
