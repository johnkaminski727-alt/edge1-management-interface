#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${COOKIE_MONSTER_REPO_ROOT:-/opt/edge1-management-interface}"
SOURCE_ROOT="$ROOT/src/web/cookie-monster"
OPERATOR_VIEW="${COOKIE_MONSTER_OPERATOR_VIEW:-/var/lib/cookie-monster-alpha/operator-view}"
DEST_ROOT="${COOKIE_MONSTER_WEB_ROOT:-/var/www/edge1-status/cookie-monster}"
MODE="${1:-}"

STATIC_FILES=("index.html" "assets/mascot.webp")
RUNTIME_FILES=("status.json" "review-state.json" "job-status.json" "acceptance.json")

for rel in "${STATIC_FILES[@]}"; do
    if [ ! -f "$SOURCE_ROOT/$rel" ]; then
        echo "Missing static source: $SOURCE_ROOT/$rel" >&2
        exit 1
    fi
    if [ -L "$SOURCE_ROOT/$rel" ]; then
        echo "Refusing symlink static source: $SOURCE_ROOT/$rel" >&2
        exit 1
    fi
done

if [ -e "$OPERATOR_VIEW" ] && [ -L "$OPERATOR_VIEW" ]; then
    echo "Refusing symlink operator-view root: $OPERATOR_VIEW" >&2
    exit 1
fi

python3 - "$OPERATOR_VIEW" <<'PY'
import json
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
for name in ("status.json", "review-state.json", "job-status.json", "acceptance.json"):
    path = root / name
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"invalid runtime evidence path: {path}")
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise SystemExit(f"runtime evidence must be a JSON object: {path}")
PY

case "$MODE" in
    "")
        echo "Cookie Monster publish preflight passed."
        echo "static_source=$SOURCE_ROOT"
        echo "operator_view_source=$OPERATOR_VIEW"
        echo "destination=$DEST_ROOT"
        echo "runtime_evidence_present=$(find "$OPERATOR_VIEW" -maxdepth 1 -type f \( -name 'status.json' -o -name 'review-state.json' -o -name 'job-status.json' -o -name 'acceptance.json' \) 2>/dev/null | wc -l)"
        echo "Use --apply only after the intended Edge1 checkout and staging evidence are verified."
        exit 0
        ;;
    --apply) ;;
    *) echo "unknown argument: $MODE" >&2; exit 1 ;;
esac

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/wwcx-cookie-monster-$STAMP"
sudo mkdir -p "$BACKUP" "$DEST_ROOT/assets"

backup_one() {
    local source="$1" rel="$2"
    local backup="$BACKUP/$rel"
    sudo mkdir -p "$(dirname "$backup")"
    if sudo test -f "$source"; then
        sudo cp -a "$source" "$backup"
        printf '1\n' | sudo tee "$backup.present" >/dev/null
    else
        printf '0\n' | sudo tee "$backup.present" >/dev/null
    fi
}

for rel in "${STATIC_FILES[@]}" "${RUNTIME_FILES[@]}"; do
    backup_one "$DEST_ROOT/$rel" "$rel"
done

cat <<'ROLLBACK' | sudo tee "$BACKUP/rollback.sh" >/dev/null
#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DEST_ROOT="/var/www/edge1-status/cookie-monster"
restore_one() {
    local rel="$1"
    local source="$HERE/$rel"
    local dest="$DEST_ROOT/$rel"
    mkdir -p "$(dirname "$dest")"
    if [ "$(cat "$source.present")" = "1" ]; then
        install -m 0644 "$source" "$dest"
    else
        rm -f "$dest"
    fi
}
for rel in index.html assets/mascot.webp status.json review-state.json job-status.json acceptance.json; do
    restore_one "$rel"
done
echo "Cookie Monster rollback restored from $HERE"
ROLLBACK
sudo chmod 0750 "$BACKUP/rollback.sh"

sudo install -m 0644 "$SOURCE_ROOT/index.html" "$DEST_ROOT/index.html"
sudo install -m 0644 "$SOURCE_ROOT/assets/mascot.webp" "$DEST_ROOT/assets/mascot.webp"

for rel in "${RUNTIME_FILES[@]}"; do
    if [ -f "$OPERATOR_VIEW/$rel" ]; then
        sudo install -m 0644 "$OPERATOR_VIEW/$rel" "$DEST_ROOT/$rel"
    else
        sudo rm -f "$DEST_ROOT/$rel"
    fi
done

echo "Published Cookie Monster operator UI and bounded runtime JSON views."
echo "destination=$DEST_ROOT"
echo "rollback_backup=$BACKUP"
echo "rollback_script=$BACKUP/rollback.sh"
