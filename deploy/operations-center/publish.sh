#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/edge1-management-interface"
SOURCE="$ROOT/src/web/operations-center/index.html"
SHELL_ROOT="$ROOT/src/web/operator-shell"
REGISTRY="$ROOT/config/edge1_operator/navigation_registry.json"
DEST_ROOT="/var/www/edge1-status"
DEST="/var/www/edge1-status/index.html"
DEST_SHELL="$DEST_ROOT/operator-shell"
MODE="${1:-}"

for path in "$SOURCE" "$SHELL_ROOT/shell.css" "$SHELL_ROOT/shell.js" "$REGISTRY"; do
    if [ ! -f "$path" ]; then
        echo "Missing source: $path" >&2
        exit 1
    fi
done

case "$MODE" in
    "")
        echo "Operations Center publish preflight passed. Use --apply to publish the page and read-only operator shell assets."
        exit 0
        ;;
    --apply) ;;
    *) echo "unknown argument: $MODE" >&2; exit 1 ;;
esac

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/wwcx-operations-center-$STAMP"
sudo mkdir -p "$BACKUP" "$DEST_SHELL"

backup_one() {
    local source="$1" name="$2"
    if sudo test -f "$source"; then
        sudo cp -a "$source" "$BACKUP/$name"
        printf '1\n' | sudo tee "$BACKUP/$name.present" >/dev/null
    else
        printf '0\n' | sudo tee "$BACKUP/$name.present" >/dev/null
    fi
}

backup_one "$DEST" index.html
backup_one "$DEST_SHELL/shell.css" shell.css
backup_one "$DEST_SHELL/shell.js" shell.js
backup_one "$DEST_SHELL/navigation.json" navigation.json

cat <<'ROLLBACK' | sudo tee "$BACKUP/rollback.sh" >/dev/null
#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DEST_ROOT="/var/www/edge1-status"
DEST_SHELL="$DEST_ROOT/operator-shell"
restore_one() {
    local name="$1" dest="$2"
    if [ "$(cat "$HERE/$name.present")" = "1" ]; then
        install -m 0644 "$HERE/$name" "$dest"
    else
        rm -f "$dest"
    fi
}
mkdir -p "$DEST_SHELL"
restore_one index.html "$DEST_ROOT/index.html"
restore_one shell.css "$DEST_SHELL/shell.css"
restore_one shell.js "$DEST_SHELL/shell.js"
restore_one navigation.json "$DEST_SHELL/navigation.json"
echo "Operations Center rollback restored from $HERE"
ROLLBACK
sudo chmod 0750 "$BACKUP/rollback.sh"

sudo install -m 0644 "$SOURCE" "$DEST"
sudo install -m 0644 "$SHELL_ROOT/shell.css" "$DEST_SHELL/shell.css"
sudo install -m 0644 "$SHELL_ROOT/shell.js" "$DEST_SHELL/shell.js"
sudo install -m 0644 "$REGISTRY" "$DEST_SHELL/navigation.json"

echo "Published Operations Center and operator shell assets."
echo "destination=$DEST"
echo "rollback_backup=$BACKUP"
echo "rollback_script=$BACKUP/rollback.sh"
