#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

MODE="${1:---preflight}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$SCRIPT_DIR/templates"

ADMIN_ROOT="${WWCX_ADMIN_ROOT:-$HOME/public_html/admin}"
PUBLIC_ROOT="$(dirname "$ADMIN_ROOT")"
AUTH_LIBRARY="$PUBLIC_ROOT/includes/store-lib.php"
NAVIGATION_FILE="$ADMIN_ROOT/index.php"

SOURCE_PAGE="$SOURCE_ROOT/electrum.php"
SOURCE_API="$SOURCE_ROOT/api/electrum-status.php"

TARGET_PAGE="$ADMIN_ROOT/electrum.php"
TARGET_API_DIR="$ADMIN_ROOT/api"
TARGET_API="$TARGET_API_DIR/electrum-status.php"

BACKUP_ROOT="${WWCX_BACKUP_ROOT:-$HOME/backups/wwcx-admin-electrum}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

preflight() {
    echo "=== WW.CX ELECTRUM PREFLIGHT ==="

    test -d "$ADMIN_ROOT" ||
        fail "Missing admin directory: $ADMIN_ROOT"

    test -f "$AUTH_LIBRARY" ||
        fail "Missing authentication library: $AUTH_LIBRARY"

    test -f "$NAVIGATION_FILE" ||
        fail "Missing global admin page: $NAVIGATION_FILE"

    test -f "$SOURCE_PAGE" ||
        fail "Missing source page: $SOURCE_PAGE"

    test -f "$SOURCE_API" ||
        fail "Missing source API: $SOURCE_API"

    grep -q "function wwcx_require_user" "$AUTH_LIBRARY" ||
        fail "Authorization helper missing from $AUTH_LIBRARY"

    grep -q '<nav aria-label="Administration">' "$NAVIGATION_FILE" ||
        fail "Global administration navigation not found"

    grep -q "includes/store-lib.php" "$SOURCE_PAGE" ||
        fail "Page does not load the WW.CX authentication library"

    grep -q "wwcx_session_start()" "$SOURCE_PAGE" ||
        fail "Page does not start the WW.CX session"

    grep -q "wwcx_require_user('admin')" "$SOURCE_PAGE" ||
        fail "Page does not require an administrator"

    grep -q "includes/store-lib.php" "$SOURCE_API" ||
        fail "API does not load the WW.CX authentication library"

    grep -q "wwcx_session_start()" "$SOURCE_API" ||
        fail "API does not start the WW.CX session"

    grep -q "wwcx_require_user('admin')" "$SOURCE_API" ||
        fail "API does not require an administrator"

    echo
    echo "=== PHP SYNTAX ==="
    php -l "$SOURCE_PAGE"
    php -l "$SOURCE_API"

    echo
    echo "=== TARGET STATE ==="
    if test -e "$TARGET_PAGE"; then
        echo "Existing target: $TARGET_PAGE"
    else
        echo "New target: $TARGET_PAGE"
    fi

    if test -e "$TARGET_API"; then
        echo "Existing target: $TARGET_API"
    else
        echo "New target: $TARGET_API"
    fi

    echo
    echo "=== NAVIGATION LOCATION ==="
    grep -n -A25 -B2 \
        '<nav aria-label="Administration">' \
        "$NAVIGATION_FILE" |
        sed -n '1,50p'

    echo
    echo "Preflight passed."
    echo "No live files were changed."
}

backup_file() {
    local source="$1"
    local relative="$2"

    if test -e "$source"; then
        mkdir -p "$BACKUP_DIR/$(dirname "$relative")"
        cp -a "$source" "$BACKUP_DIR/$relative"
    fi
}

apply_installation() {
    preflight

    echo
    echo "=== CREATE BACKUP ==="
    mkdir -p "$BACKUP_DIR"

    backup_file "$TARGET_PAGE" "admin/electrum.php"
    backup_file "$TARGET_API" "admin/api/electrum-status.php"

    printf '%s\n' \
        "created_at=$STAMP" \
        "admin_root=$ADMIN_ROOT" \
        "target_page=$TARGET_PAGE" \
        "target_api=$TARGET_API" \
        > "$BACKUP_DIR/manifest.txt"

    echo "Backup directory: $BACKUP_DIR"

    rollback() {
        local status=$?

        if test "$status" -ne 0; then
            echo
            echo "=== AUTOMATIC ROLLBACK ===" >&2

            if test -f "$BACKUP_DIR/admin/electrum.php"; then
                cp -a "$BACKUP_DIR/admin/electrum.php" "$TARGET_PAGE"
            else
                rm -f "$TARGET_PAGE"
            fi

            if test -f "$BACKUP_DIR/admin/api/electrum-status.php"; then
                mkdir -p "$TARGET_API_DIR"
                cp -a \
                    "$BACKUP_DIR/admin/api/electrum-status.php" \
                    "$TARGET_API"
            else
                rm -f "$TARGET_API"
            fi

            echo "Rollback completed." >&2
        fi

        exit "$status"
    }

    trap rollback ERR INT TERM

    echo
    echo "=== INSTALL FILES ==="
    mkdir -p "$TARGET_API_DIR"

    install -m 0644 "$SOURCE_PAGE" "$TARGET_PAGE"
    install -m 0644 "$SOURCE_API" "$TARGET_API"

    echo
    echo "=== DEPLOYED PHP SYNTAX ==="
    php -l "$TARGET_PAGE"
    php -l "$TARGET_API"

    echo
    echo "=== VERIFY INSTALLED CONTENT ==="
    cmp -s "$SOURCE_PAGE" "$TARGET_PAGE" ||
        fail "Installed page differs from source"

    cmp -s "$SOURCE_API" "$TARGET_API" ||
        fail "Installed API differs from source"

    trap - ERR INT TERM

    echo
    echo "Installation completed."
    echo "Navigation was not modified automatically."
    echo "Backup directory: $BACKUP_DIR"
}

case "$MODE" in
    --preflight)
        preflight
        ;;
    --apply)
        apply_installation
        ;;
    *)
        fail "Usage: $0 --preflight | --apply"
        ;;
esac
