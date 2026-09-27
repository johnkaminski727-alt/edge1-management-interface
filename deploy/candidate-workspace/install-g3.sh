#!/usr/bin/env bash
# G3 strictly local preview package. Existing G1, G2 database/token, Apache,
# network collectors, firewall, systemd, DNS and production settings untouched.
set -Eeuo pipefail
umask 027
ROOT="${EDGE1_G3_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DEST="/opt/edge1-operations-workspace-g3"
BACKUPS="/var/backups/edge1-operations-workspace-g3"
G2_DATA="/var/lib/edge1-candidate-workspace-g2"
MARKER="edge1-operations-workspace-g3-local-only"
FILES=(
 "tools/operations/edge1_candidate_workspace.py"
 "tools/operations/edge1_candidate_store.py"
 "tools/operations/edge1_candidate_api.py"
 "tools/operations/edge1_operations_view.py"
 "tools/operations/edge1_host_metrics.py"
 "tools/operations/edge1_operations_api.py"
 "tools/operations/inspect_edge1_security_sources.py"
 "src/web/operations-center/operations-workspace-g3.html"
 "docs/operations-center/operations-workspace-g3.md"
)
mode="${1:---check}"
fail(){ echo "STOP: $*" >&2; exit 1; }
case "$mode" in --check|--apply|--verify) ;; *) fail "Usage: install-g3.sh [--check|--apply|--verify]";; esac
if [[ "$mode" == --verify ]]; then
  [[ -d "$DEST" && ! -L "$DEST" && -f "$DEST/INSTALL-ID" &&
    "$(cat "$DEST/INSTALL-ID")" == "$MARKER" ]] || fail "Unrecognized G3 install"
  (cd "$DEST" && sha256sum -c SHA256SUMS --quiet) || fail "G3 installed checksums failed"
  [[ -d "$G2_DATA" && ! -L "$G2_DATA" &&
     "$(stat -c %U:%a "$G2_DATA")" == wwadmin:700 ]] ||
     fail "Existing G2 private data missing or unexpectedly exposed"
  [[ -f "$G2_DATA/access-token" && ! -L "$G2_DATA/access-token" &&
     "$(stat -c %U:%a "$G2_DATA/access-token")" == wwadmin:600 ]] ||
     fail "Existing G2 private access token invalid"
  echo "PASS: G3 files verified and existing private G2 data preserved"
  exit 0
fi
echo "=== G3 offline source preflight ==="
for file in "${FILES[@]}"; do
  [[ -f "$ROOT/$file" && ! -L "$ROOT/$file" && -s "$ROOT/$file" ]] ||
    fail "Invalid source: $file"
done
python3 "$ROOT/tests/validate_edge1_candidate_workspace.py" -q
python3 "$ROOT/tests/validate_edge1_candidate_store.py" -q
python3 "$ROOT/tests/validate_edge1_candidate_api.py" -q
python3 "$ROOT/tests/validate_edge1_operations_g3.py" -q
python3 - "$ROOT/src/web/operations-center/operations-workspace-g3.html" <<'PY'
from pathlib import Path
import sys
ui=Path(sys.argv[1]).read_text(encoding="utf-8")
assert "data-tab=\"security\"" in ui and "data-tab=\"network\"" in ui
assert '"/api/operations"' in ui
assert '"/api/apply"' not in ui and "localStorage" not in ui
print("PASS: G3 multi-module UI, authenticated read-only operations endpoint; no Apply or token storage")
PY
if [[ "$mode" == --check ]]; then
 echo "PASS: G3 sources passed offline preflight; nothing installed."
 exit 0
fi
[[ "$(id -u)" == 0 && "${SUDO_USER:-}" == wwadmin ]] ||
 fail "G3 install must run through sudo from wwadmin"
[[ -d "$G2_DATA" && ! -L "$G2_DATA" &&
   "$(stat -c %U:%a "$G2_DATA")" == wwadmin:700 &&
   -f "$G2_DATA/access-token" && ! -L "$G2_DATA/access-token" &&
   "$(stat -c %U:%a "$G2_DATA/access-token")" == wwadmin:600 ]] ||
 fail "Verified G2 private installation required"
[[ ! -L "$DEST" ]] || fail "Destination symlink refused"
if [[ -e "$DEST" ]]; then
 [[ -d "$DEST" && -f "$DEST/INSTALL-ID" && ! -L "$DEST/INSTALL-ID" &&
   "$(cat "$DEST/INSTALL-ID")" == "$MARKER" &&
   "$(stat -c %U "$DEST")" == root ]] ||
 fail "Unexpected existing G3 destination"
fi
install -d -o root -g root -m 0700 "$BACKUPS"
stage="$(mktemp -d /opt/.edge1-g3-stage.XXXXXXXX)"
backup=""
cleanup(){
 rc=$?
 if [[ "$rc" -ne 0 && -n "$backup" && -d "$backup" ]]; then
   if [[ -d "$DEST" && ! -L "$DEST" && -f "$DEST/INSTALL-ID" &&
       "$(cat "$DEST/INSTALL-ID")" == "$MARKER" ]]; then rm -rf -- "$DEST"; fi
   [[ -e "$DEST" ]] || mv -- "$backup" "$DEST" || true
 fi
 [[ -z "${stage:-}" || ! -d "$stage" ]] || rm -rf -- "$stage"
 exit "$rc"
}
trap cleanup EXIT
install -m 0644 "$ROOT/tools/operations/edge1_candidate_workspace.py" "$stage/edge1_candidate_workspace.py"
install -m 0644 "$ROOT/tools/operations/edge1_candidate_store.py" "$stage/edge1_candidate_store.py"
install -m 0644 "$ROOT/tools/operations/edge1_candidate_api.py" "$stage/edge1_candidate_api.py"
install -m 0644 "$ROOT/tools/operations/edge1_operations_view.py" "$stage/edge1_operations_view.py"
install -m 0644 "$ROOT/tools/operations/edge1_host_metrics.py" "$stage/edge1_host_metrics.py"
install -m 0644 "$ROOT/tools/operations/edge1_operations_api.py" "$stage/edge1_operations_api.py"
install -m 0644 "$ROOT/tools/operations/inspect_edge1_security_sources.py" "$stage/inspect_edge1_security_sources.py"
install -m 0644 "$ROOT/src/web/operations-center/operations-workspace-g3.html" "$stage/index.html"
install -m 0644 "$ROOT/docs/operations-center/operations-workspace-g3.md" "$stage/README.md"
printf '%s\n' "$MARKER" >"$stage/INSTALL-ID"
(cd "$stage" && sha256sum edge1_candidate_workspace.py edge1_candidate_store.py edge1_candidate_api.py edge1_operations_view.py edge1_host_metrics.py edge1_operations_api.py inspect_edge1_security_sources.py index.html README.md >SHA256SUMS)
if [[ -d "$DEST" ]]; then
 backup="$BACKUPS/$(date -u +%Y%m%dT%H%M%SZ)-$$"
 mv -- "$DEST" "$backup"
fi
mv -- "$stage" "$DEST";stage=""
chown -R root:root "$DEST";chmod 0755 "$DEST"
(cd "$DEST" && sha256sum -c SHA256SUMS --quiet) || fail "G3 post-install checksum mismatch"
echo "PASS: Installed G3 private operations UI under $DEST"
echo "Existing G1/G2 files, G2 candidate data/token and production network unchanged."
echo "No listeners or persistent services were started."
