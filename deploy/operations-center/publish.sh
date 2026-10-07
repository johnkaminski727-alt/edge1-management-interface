#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=/opt/edge1-management-interface
DEST=/var/www/edge1-status
MODE="${1:-}"

declare -a FILES=(
  "src/web/branding/favicon.svg|favicon.svg"
  "src/web/branding/favicon.ico|favicon.ico"
  "src/web/branding/favicon-16.png|favicon-16.png"
  "src/web/branding/favicon-32.png|favicon-32.png"
  "src/web/branding/apple-touch-icon.png|apple-touch-icon.png"
  "src/web/branding/site.webmanifest|site.webmanifest"
  "src/web/operations-center/index.html|index.html"
  "src/web/operations-center/core-dashboard.js|core-dashboard.js"
  "src/web/operations-center/crowdsec-dashboard.js|crowdsec-dashboard.js"
  "src/web/security/index.html|security/index.html"
  "src/web/security/correlation.html|security/correlation.html"
  "src/web/security/crowdsec-dashboard.js|security/crowdsec-dashboard.js"
  "src/web/network-defense/index.html|network-defense/index.html"
  "src/web/operator-shell/shell.css|operator-shell/shell.css"
  "src/web/operator-shell/theme.css|operator-shell/theme.css"
  "src/web/operator-shell/shell.js|operator-shell/shell.js"
  "config/edge1_operator/navigation_registry.json|operator-shell/navigation.json"
  "src/web/edge1-ops/ava/index.html|ava/index.html"
  "src/web/time-authority/index.html|time-authority/index.html"
  "src/web/time-authority/app.js|time-authority/app.js"
  "src/web/time-authority/styles.css|time-authority/styles.css"
)

NAV_DB=/var/lib/edge1-navigation/navigation.sqlite3
NAV_TOOL="$ROOT/tools/edge1_operator/navigation_db.py"
NAV_VALIDATE="$ROOT/tools/edge1_operator/validate_navigation_registry.py"
NAV_PREFLIGHT="$(mktemp /tmp/edge1-navigation-preflight.XXXXXX.json)"
trap 'rm -f "$NAV_PREFLIGHT"' EXIT

echo "=== Database-backed navigation preflight ==="
if test -s "$NAV_DB"; then
    /usr/bin/python3 "$NAV_TOOL" --database "$NAV_DB" export --output "$NAV_PREFLIGHT" >/dev/null
    /usr/bin/python3 "$NAV_VALIDATE" "$NAV_PREFLIGHT"
else
    echo "INFO: navigation database not commissioned yet; bootstrap registry will be published."
fi

echo "=== Unified Operations Center preflight ==="
for entry in "${FILES[@]}"; do
    source="${entry%%|*}"
    test -s "$ROOT/$source" || {
        echo "STOP: Missing source: $source" >&2
        exit 1
    }
done

case "$MODE" in
    "")
        echo "PASS: All deployment assets present."
        echo "Use --apply for deployment."
        exit 0
        ;;
    --apply) ;;
    *)
        echo "Usage: $0 [--apply]" >&2
        exit 2
        ;;
esac

test "$(id -u)" -eq 0 || {
    echo "STOP: --apply requires root" >&2
    exit 1
}

/usr/bin/python3 "$ROOT/tools/edge1_operator/check_ui_publication.py" check

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/edge1-unified-publish-$STAMP"
mkdir -p "$BACKUP/previous"
chmod 0700 "$BACKUP"

# Build the full backup before publishing any file.
: >"$BACKUP/manifest"
for entry in "${FILES[@]}"; do
    source="${entry%%|*}"
    relative="${entry#*|}"
    target="$DEST/$relative"
    if test -f "$target"; then
        mkdir -p "$BACKUP/previous/$(dirname "$relative")"
        cp -a "$target" "$BACKUP/previous/$relative"
        printf 'present|%s\n' "$relative" >>"$BACKUP/manifest"
    elif ! test -e "$target"; then
        printf 'absent|%s\n' "$relative" >>"$BACKUP/manifest"
    else
        echo "STOP: Destination is not a regular file: $target" >&2
        exit 1
    fi
done

cat >"$BACKUP/rollback.sh" <<'ROLLBACK'
#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST=/var/www/edge1-status

while IFS='|' read -r state relative; do
    target="$DEST/$relative"
    if [ "$state" = present ]; then
        install -d -m 0755 "$(dirname "$target")"
        install -m 0644 "$HERE/previous/$relative" "$target"
    elif [ "$state" = absent ]; then
        rm -f "$target"
    else
        echo "Invalid rollback manifest" >&2
        exit 1
    fi
done <"$HERE/manifest"

echo "Previous interface restored: $HERE"
ROLLBACK
chmod 0700 "$BACKUP/rollback.sh"

echo "=== Publishing interface assets ==="
for entry in "${FILES[@]}"; do
    source="${entry%%|*}"
    relative="${entry#*|}"
    target="$DEST/$relative"
    install -d -m 0755 "$(dirname "$target")"
    install -m 0644 "$ROOT/$source" "$target"
    echo "Published: $relative"
done

if test -s "$NAV_DB"; then
    echo "=== Restoring database as navigation source of truth ==="
    /usr/bin/python3 "$NAV_TOOL" --database "$NAV_DB" export --output "$DEST/operator-shell/navigation.json"
    /usr/bin/python3 "$NAV_VALIDATE" "$DEST/operator-shell/navigation.json"
fi

/usr/bin/python3 "$ROOT/tools/edge1_operator/check_ui_publication.py" record

echo "PASS: Unified interface published."
echo "Rollback: $BACKUP/rollback.sh"
echo "Runtime JSON snapshots and monitoring services were not changed."
