#!/bin/sh
set -eu
umask 077

TARGET=${EDGE1_SYSTEMD_UNIT_DIR:-/etc/systemd/system}
EXPECTED_HOST=${EDGE1_EXPECTED_HOST:-edge1.ww.cx}
EXPECTED_BAD_OWNER=${EDGE1_EXPECTED_BAD_UNIT_DIR_OWNER:-bigbird-time:bigbird-time}
EXPECTED_BAD_MODE=${EDGE1_EXPECTED_BAD_UNIT_DIR_MODE:-750}
DESIRED_OWNER=root:root
DESIRED_MODE=755
EVIDENCE_ROOT=${EDGE1_SYSTEMD_BOUNDARY_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/systemd-unit-dir-boundary}
MODE=${1:-}

fail() {
    echo "EDGE1_SYSTEMD_UNIT_DIR_REPAIR=FAIL" >&2
    echo "reason=$*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root"
[ "$(hostname -f)" = "$EXPECTED_HOST" ] || fail "wrong host: $(hostname -f)"
[ "$TARGET" = "/etc/systemd/system" ] || fail "unexpected target: $TARGET"
[ -d "$TARGET" ] || fail "target directory missing: $TARGET"
for command_name in stat chown chmod install systemctl find sort cmp sha256sum runuser; do
    command -v "$command_name" >/dev/null 2>&1 || fail "$command_name unavailable"
done

owner=$(stat -c '%U:%G' "$TARGET")
mode=$(stat -c '%a' "$TARGET")

echo "target=$TARGET"
echo "current_owner=$owner"
echo "current_mode=$mode"
echo "desired_owner=$DESIRED_OWNER"
echo "desired_mode=$DESIRED_MODE"

if [ "$owner" = "$DESIRED_OWNER" ] && [ "$mode" = "$DESIRED_MODE" ]; then
    echo "status=already_safe"
    echo "EDGE1_SYSTEMD_UNIT_DIR_REPAIR=PASS"
    exit 0
fi

[ "$owner" = "$EXPECTED_BAD_OWNER" ] || fail "unexpected current owner: $owner"
[ "$mode" = "$EXPECTED_BAD_MODE" ] || fail "unexpected current mode: $mode"

case "$MODE" in
    "")
        echo "status=dry_run"
        echo "would_change_owner=$EXPECTED_BAD_OWNER->$DESIRED_OWNER"
        echo "would_change_mode=$EXPECTED_BAD_MODE->$DESIRED_MODE"
        echo "No files, services, listeners, or unit contents would be changed."
        echo "Run with --apply only after explicit production security-change approval."
        exit 0
        ;;
    --apply) ;;
    *) fail "usage: $0 [--apply]" ;;
esac

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
if [ ! -d "$EVIDENCE_ROOT" ]; then
    install -d -o root -g root -m 0700 "$EVIDENCE_ROOT"
fi
install -d -o root -g root -m 0700 "$EVIDENCE_DIR"

{
    echo "captured_at_utc=$STAMP"
    echo "host=$(hostname -f)"
    echo "target=$TARGET"
    stat -c 'before_owner=%U:%G' "$TARGET"
    stat -c 'before_mode=%a' "$TARGET"
    stat -c 'before_inode=%i' "$TARGET"
} >"$EVIDENCE_DIR/before.txt"

if command -v namei >/dev/null 2>&1; then
    namei -l "$TARGET" >"$EVIDENCE_DIR/namei-before.txt" 2>&1 || true
else
    echo "namei_unavailable=true" >"$EVIDENCE_DIR/namei-before.txt"
fi
find "$TARGET" -mindepth 1 -maxdepth 1 -printf '%f\t%y\t%u:%g\t%m\n' \
    | LC_ALL=C sort >"$EVIDENCE_DIR/entries-before.tsv"

for unit in \
    edge1-time-authority-dashboard.service \
    edge1-time-authority-collector.timer \
    edge1-operator-mcp.service \
    edge1-secure-mcp-tunnel.service \
    bigbird-ai-tunnel.service; do
    {
        printf '%s\tactive=' "$unit"
        systemctl is-active "$unit" 2>/dev/null || true
        printf '%s\tenabled=' "$unit"
        systemctl is-enabled "$unit" 2>/dev/null || true
    } >>"$EVIDENCE_DIR/services-before.txt"
done

cat >"$EVIDENCE_DIR/rollback.sh" <<EOF
#!/bin/sh
set -eu
TARGET='$TARGET'
[ "\$(id -u)" -eq 0 ] || { echo 'run as root' >&2; exit 1; }
[ "\$(stat -c '%U:%G' "\$TARGET")" = '$DESIRED_OWNER' ] || { echo 'refusing rollback: unexpected owner' >&2; exit 1; }
[ "\$(stat -c '%a' "\$TARGET")" = '$DESIRED_MODE' ] || { echo 'refusing rollback: unexpected mode' >&2; exit 1; }
chown '$EXPECTED_BAD_OWNER' "\$TARGET"
chmod '$EXPECTED_BAD_MODE' "\$TARGET"
echo 'WARNING: emergency rollback restored the prior service-account-owned systemd directory state.'
EOF
chmod 0700 "$EVIDENCE_DIR/rollback.sh"

# Smallest possible live change: parent directory metadata only. Unit contents,
# symlinks, services, listeners, and the systemd manager are not changed.
chown "$DESIRED_OWNER" "$TARGET"
chmod "$DESIRED_MODE" "$TARGET"

owner_after=$(stat -c '%U:%G' "$TARGET")
mode_after=$(stat -c '%a' "$TARGET")
[ "$owner_after" = "$DESIRED_OWNER" ] || fail "post-change owner verification failed: $owner_after"
[ "$mode_after" = "$DESIRED_MODE" ] || fail "post-change mode verification failed: $mode_after"

{
    echo "completed_at_utc=$(date -u +%Y%m%dT%H%M%SZ)"
    echo "after_owner=$owner_after"
    echo "after_mode=$mode_after"
    stat -c 'after_inode=%i' "$TARGET"
} >"$EVIDENCE_DIR/after.txt"

if command -v namei >/dev/null 2>&1; then
    namei -l "$TARGET" >"$EVIDENCE_DIR/namei-after.txt" 2>&1 || true
else
    echo "namei_unavailable=true" >"$EVIDENCE_DIR/namei-after.txt"
fi
find "$TARGET" -mindepth 1 -maxdepth 1 -printf '%f\t%y\t%u:%g\t%m\n' \
    | LC_ALL=C sort >"$EVIDENCE_DIR/entries-after.tsv"

cmp -s "$EVIDENCE_DIR/entries-before.tsv" "$EVIDENCE_DIR/entries-after.tsv" || \
    fail "unit-directory entries changed unexpectedly"

for unit in \
    edge1-time-authority-dashboard.service \
    edge1-time-authority-collector.timer \
    edge1-operator-mcp.service \
    edge1-secure-mcp-tunnel.service \
    bigbird-ai-tunnel.service; do
    {
        printf '%s\tactive=' "$unit"
        systemctl is-active "$unit" 2>/dev/null || true
        printf '%s\tenabled=' "$unit"
        systemctl is-enabled "$unit" 2>/dev/null || true
    } >>"$EVIDENCE_DIR/services-after.txt"
done

cmp -s "$EVIDENCE_DIR/services-before.txt" "$EVIDENCE_DIR/services-after.txt" || \
    fail "service active/enabled state changed unexpectedly"

if [ -f "$TARGET/edge1-secure-mcp-tunnel.service" ]; then
    test -r "$TARGET/edge1-secure-mcp-tunnel.service" || fail "root can no longer read tunnel unit"
    if id edge1-operator >/dev/null 2>&1; then
        runuser -u edge1-operator -- test -r "$TARGET/edge1-secure-mcp-tunnel.service" || \
            fail "edge1-operator still cannot read the world-readable tunnel unit after safe directory restoration"
    fi
fi

sha256sum "$EVIDENCE_DIR"/*.txt "$EVIDENCE_DIR"/*.tsv >"$EVIDENCE_DIR/SHA256SUMS"

echo "evidence_dir=$EVIDENCE_DIR"
echo "status=applied"
echo "live_configuration_changed=directory_metadata_only"
echo "service_state_changed=false"
echo "unit_contents_changed=false"
echo "EDGE1_SYSTEMD_UNIT_DIR_REPAIR=PASS"
