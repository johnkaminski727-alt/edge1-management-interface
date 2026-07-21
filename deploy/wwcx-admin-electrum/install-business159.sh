#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$REPO_ROOT/deploy/wwcx-admin-electrum/templates"
ADMIN="${WWCX_ADMIN_ROOT:-$HOME/public_html/admin}"
BACKUPS="${WWCX_BACKUP_ROOT:-$HOME/backups/wwcx-admin-electrum}"
MODE="${1:---preflight}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST_PAGE="$ADMIN/electrum.php"
DEST_API="$ADMIN/api/electrum-status.php"

fail() { echo "ERROR: $*" >&2; exit 1; }
check() {
  test -d "$ADMIN" || fail "Missing admin root: $ADMIN"
  test -f "$ADMIN/bootstrap.php" || fail "Missing admin bootstrap: $ADMIN/bootstrap.php"
  test -f "$SRC/electrum.php" || fail "Missing template: $SRC/electrum.php"
  test -f "$SRC/api/electrum-status.php" || fail "Missing template: $SRC/api/electrum-status.php"
  grep -q "wwcx_require_user('admin')" "$SRC/electrum.php" || fail "Page lacks admin guard"
  grep -q "wwcx_require_user('admin')" "$SRC/api/electrum-status.php" || fail "API lacks admin guard"
  php -l "$SRC/electrum.php"
  php -l "$SRC/api/electrum-status.php"
}

case "$MODE" in
  --preflight)
    check
    echo "Admin root: $ADMIN"
    echo "Existing Electrum page: $(test -e "$DEST_PAGE" && echo yes || echo no)"
    echo "Existing Electrum API: $(test -e "$DEST_API" && echo yes || echo no)"
    echo "Navigation candidates:"
    grep -RIl --exclude='electrum.php' -E 'Dashboard|BigBird|Print Production|admin navigation' "$ADMIN" 2>/dev/null | head -20 || true
    echo "Preflight passed; no live files changed."
    ;;
  --install)
    check
    mkdir -p "$BACKUPS/$STAMP" "$ADMIN/api"
    for target in "$DEST_PAGE" "$DEST_API"; do
      if test -e "$target"; then
        cp -a "$target" "$BACKUPS/$STAMP/$(basename "$target").before"
      fi
    done
    install -m 0644 "$SRC/electrum.php" "$DEST_PAGE"
    install -m 0644 "$SRC/api/electrum-status.php" "$DEST_API"
    php -l "$DEST_PAGE"
    php -l "$DEST_API"
    echo "$BACKUPS/$STAMP" > "$BACKUPS/latest-backup"
    echo "Installed Electrum module. Navigation and secret configuration remain manual."
    echo "Backup: $BACKUPS/$STAMP"
    ;;
  --rollback)
    test -f "$BACKUPS/latest-backup" || fail "No recorded backup"
    B="$(cat "$BACKUPS/latest-backup")"
    test -d "$B" || fail "Missing backup directory: $B"
    if test -f "$B/electrum.php.before"; then cp -a "$B/electrum.php.before" "$DEST_PAGE"; else rm -f "$DEST_PAGE"; fi
    if test -f "$B/electrum-status.php.before"; then cp -a "$B/electrum-status.php.before" "$DEST_API"; else rm -f "$DEST_API"; fi
    echo "Rollback completed from $B"
    ;;
  *)
    fail "Usage: $0 --preflight|--install|--rollback"
    ;;
esac
