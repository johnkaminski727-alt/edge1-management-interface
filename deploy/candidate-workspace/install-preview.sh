#!/usr/bin/env bash
# Edge1 G1 local-only candidate workspace preview installer.
# Install only the immutable offline prototype under /opt; no Apache, firewall,
# service, routing, DNS, or production configuration changes are permitted.
set -Eeuo pipefail
umask 027

ROOT="${EDGE1_G1_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DEST="/opt/edge1-candidate-workspace-g1"
BACKUP_ROOT="/var/backups/edge1-candidate-workspace-g1"
FILES=(
  "src/web/operations-center/candidate-workspace-preview.html"
  "tools/operations/edge1_candidate_workspace.py"
  "docs/operations-center/candidate-workspace-g1.md"
  "tests/validate_edge1_candidate_workspace.py"
)
MARKER="edge1-candidate-workspace-g1-local-preview"
MODE="${1:---check}"

fail() { echo "STOP: $*" >&2; exit 1; }
preflight() {
    for file in "${FILES[@]}"; do
        [[ -f "$ROOT/$file" && ! -L "$ROOT/$file" && -s "$ROOT/$file" ]] ||
            fail "Missing, empty or symlinked source: $file"
    done
    /usr/bin/python3 "$ROOT/tests/validate_edge1_candidate_workspace.py" -q
    /usr/bin/grep -Fq 'OFFLINE · NO PRODUCTION CONNECTION' "$ROOT/src/web/operations-center/candidate-workspace-preview.html" ||
        fail "Offline-only UI warning missing"
    /usr/bin/python3 - "$ROOT/src/web/operations-center/candidate-workspace-preview.html" <<'PY'
from pathlib import Path
import sys
html = Path(sys.argv[1]).read_text()
assert "fetch(" not in html and "XMLHttpRequest" not in html
assert "<script src=" not in html and "type=\"module\"" not in html
assert "Apply changes</button>" not in html
print("PASS: No network requests or live Apply controls in offline preview")
PY
}

[[ "$MODE" == --check || "$MODE" == --apply || "$MODE" == --verify ]] ||
    fail "Usage: install-preview.sh [--check|--apply|--verify]"
if [[ "$MODE" == --verify ]]; then
    [[ -d "$DEST" && ! -L "$DEST" ]] || fail "G1 preview not installed"
    [[ "$(/usr/bin/cat "$DEST/INSTALL-ID")" == "$MARKER" ]] || fail "Unrecognized installation marker"
    /usr/bin/sha256sum -c "$DEST/SHA256SUMS" --quiet --ignore-missing
    /usr/bin/python3 -m py_compile "$DEST/edge1_candidate_workspace.py"
    echo "PASS: Local-only G1 preview installed; recorded payload hashes verified"
    exit 0
fi

echo "=== Edge1 G1 local-only preview: source preflight ==="
preflight
if [[ "$MODE" == --check ]]; then
    echo "PASS: G1 source validated. Nothing installed. Use --apply after review."
    exit 0
fi
[[ "$(/usr/bin/id -u)" -eq 0 ]] || fail "--apply requires sudo/root"
[[ ! -L "$DEST" ]] || fail "Destination is a symlink"
if [[ -e "$DEST" ]]; then
    [[ -d "$DEST" && -f "$DEST/INSTALL-ID" &&
       "$(/usr/bin/cat "$DEST/INSTALL-ID")" == "$MARKER" ]] ||
        fail "Unrecognized existing destination; refusing replacement"
    [[ "$(/usr/bin/stat -c %u "$DEST")" == 0 ]] ||
        fail "Existing installation must be root-owned"
fi

/usr/bin/install -d -m 0750 "$BACKUP_ROOT"
STAGE="$(/usr/bin/mktemp -d /opt/.edge1-g1-stage.XXXXXXXX)"
moved=0
restore() {
    rc=$?
    if [[ "$rc" -ne 0 && "$moved" -eq 1 && ! -e "$DEST" && -n "${BACKUP:-}" && -d "$BACKUP" ]]; then
        /usr/bin/mv -- "$BACKUP" "$DEST" || true
    fi
    if [[ -n "${STAGE:-}" && -d "$STAGE" ]]; then /usr/bin/rm -rf -- "$STAGE"; fi
    exit "$rc"
}
trap restore EXIT

/usr/bin/install -m 0644 "$ROOT/src/web/operations-center/candidate-workspace-preview.html" "$STAGE/index.html"
/usr/bin/install -m 0644 "$ROOT/tools/operations/edge1_candidate_workspace.py" "$STAGE/edge1_candidate_workspace.py"
/usr/bin/install -m 0644 "$ROOT/docs/operations-center/candidate-workspace-g1.md" "$STAGE/README.md"
/usr/bin/install -m 0644 "$ROOT/tests/validate_edge1_candidate_workspace.py" "$STAGE/validate_edge1_candidate_workspace.py"
/usr/bin/printf '%s\n' "$MARKER" > "$STAGE/INSTALL-ID"
(
  cd "$STAGE"
  /usr/bin/sha256sum index.html edge1_candidate_workspace.py README.md validate_edge1_candidate_workspace.py > SHA256SUMS
)
echo "=== Installing G1 under $DEST ==="
if [[ -d "$DEST" ]]; then
    STAMP="$(/usr/bin/date -u +%Y%m%dT%H%M%SZ)-$$"
    BACKUP="$BACKUP_ROOT/$STAMP"
    /usr/bin/mv -- "$DEST" "$BACKUP"
    moved=1
fi
/usr/bin/mv -- "$STAGE" "$DEST"
STAGE=""
/usr/bin/chown -R root:root "$DEST"
/usr/bin/chmod 0755 "$DEST"
/usr/bin/sha256sum -c "$DEST/SHA256SUMS" --quiet --ignore-missing
echo "PASS: Installed isolated local preview; existing production services untouched"
echo "Location: $DEST"
if [[ -n "${BACKUP:-}" ]]; then echo "Previous G1 installation: $BACKUP"; fi
echo "Access requires a separately started loopback-only HTTP server and an SSH tunnel."
