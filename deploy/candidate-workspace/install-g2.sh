#!/usr/bin/env bash
# G2 opt-in local-only install. No daemon, Apache, firewall or live config changes.
set -Eeuo pipefail
umask 077

ROOT="${EDGE1_G2_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DEST="/opt/edge1-candidate-workspace-g2"
DATA="/var/lib/edge1-candidate-workspace-g2"
BACKUPS="/var/backups/edge1-candidate-workspace-g2"
MARK="edge1-g2-private-candidate-preview"
MODE="${1:---check}"
fail(){ echo "STOP: $*" >&2; exit 1; }

case "$MODE" in --check|--apply|--verify) ;; *) fail "Usage: install-g2.sh [--check|--apply|--verify]" ;; esac

if [[ "$MODE" == --verify ]]; then
    [[ -d "$DEST" && ! -L "$DEST" && -f "$DEST/INSTALL-ID" ]] || fail "G2 missing"
    [[ "$(cat "$DEST/INSTALL-ID")" == "$MARK" ]] || fail "Unrecognized installation"
    (cd "$DEST" && sha256sum -c SHA256SUMS --quiet) || fail "Installed source checksum mismatch"
    [[ -d "$DATA" && ! -L "$DATA" && -f "$DATA/access-token" && ! -L "$DATA/access-token" ]] ||
        fail "Private data or token file missing"
    [[ "$(stat -c %a "$DATA")" == 700 && "$(stat -c %a "$DATA/access-token")" == 600 ]] ||
        fail "Incorrect private data or token permissions"
    [[ "$(stat -c %U "$DATA")" == wwadmin && "$(stat -c %U "$DATA/access-token")" == wwadmin ]] ||
        fail "Private files must be owned by wwadmin"
    echo "PASS: G2 local package hashes and private-token permissions verified"
    exit 0
fi

echo "=== G2 offline source preflight ==="
SOURCES=(
 "tools/operations/edge1_candidate_workspace.py"
 "tools/operations/edge1_candidate_store.py"
 "tools/operations/edge1_candidate_api.py"
 "src/web/operations-center/candidate-workspace-g2.html"
 "tests/validate_edge1_candidate_workspace.py"
 "tests/validate_edge1_candidate_store.py"
 "tests/validate_edge1_candidate_api.py"
 "docs/operations-center/candidate-workspace-g2.md"
)
for src in "${SOURCES[@]}"; do
    [[ -s "$ROOT/$src" && -f "$ROOT/$src" && ! -L "$ROOT/$src" ]] ||
        fail "Missing, empty or symlinked source: $src"
done
python3 "$ROOT/tests/validate_edge1_candidate_workspace.py" -q
python3 "$ROOT/tests/validate_edge1_candidate_store.py" -q
python3 "$ROOT/tests/validate_edge1_candidate_api.py" -q
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
api=(root/"tools/operations/edge1_candidate_api.py").read_text()
ui=(root/"src/web/operations-center/candidate-workspace-g2.html").read_text()
assert '("127.0.0.1", args.port)' in api
assert '"/api/apply"' not in api
assert 'type="password"' in ui
assert "G2 · LOCAL SSH ACCESS" in ui
print("PASS: loopback-only API, no Apply endpoint and private-token UI")
PY
if [[ "$MODE" == --check ]]; then
    echo "PASS: G2 source validated. No installation performed."
    exit 0
fi

[[ "$(id -u)" == 0 ]] || fail "--apply requires sudo"
[[ "${SUDO_USER:-}" == wwadmin ]] || fail "Installer must be invoked by wwadmin via sudo"
[[ ! -L "$DEST" && ! -L "$DATA" ]] || fail "Symlinked destination refused"
if [[ -e "$DEST" ]]; then
    [[ -d "$DEST" && -f "$DEST/INSTALL-ID" && ! -L "$DEST/INSTALL-ID" &&
      "$(cat "$DEST/INSTALL-ID")" == "$MARK" && "$(stat -c %U "$DEST")" == root ]] ||
        fail "Existing destination not recognized as root-owned G2 installation"
fi
if [[ -e "$DATA" ]]; then
    [[ -d "$DATA" && "$(stat -c %U "$DATA")" == wwadmin &&
       "$(stat -c %a "$DATA")" == 700 ]] || fail "Existing data directory ownership or mode incorrect"
fi

install -d -o root -g root -m 0700 "$BACKUPS"
stage="$(mktemp -d /opt/.edge1-g2-stage.XXXXXXXX)"
backup=""
finished=0
cleanup(){
    rc=$?
    if [[ "$rc" -ne 0 && -n "$backup" && -d "$backup" ]]; then
        if [[ -d "$DEST" && ! -L "$DEST" && -f "$DEST/INSTALL-ID" &&
          "$(cat "$DEST/INSTALL-ID")" == "$MARK" ]]; then
            rm -rf -- "$DEST"
        fi
        if [[ ! -e "$DEST" ]]; then mv -- "$backup" "$DEST" || true; fi
    fi
    [[ -z "${stage:-}" || ! -d "$stage" ]] || rm -rf -- "$stage"
    exit "$rc"
}
trap cleanup EXIT
install -m 0644 "$ROOT/tools/operations/edge1_candidate_workspace.py" "$stage/edge1_candidate_workspace.py"
install -m 0644 "$ROOT/tools/operations/edge1_candidate_store.py" "$stage/edge1_candidate_store.py"
install -m 0644 "$ROOT/tools/operations/edge1_candidate_api.py" "$stage/edge1_candidate_api.py"
install -m 0644 "$ROOT/src/web/operations-center/candidate-workspace-g2.html" "$stage/index.html"
install -m 0644 "$ROOT/docs/operations-center/candidate-workspace-g2.md" "$stage/README.md"
printf '%s\n' "$MARK" >"$stage/INSTALL-ID"
(cd "$stage" && sha256sum index.html edge1_candidate_workspace.py edge1_candidate_store.py edge1_candidate_api.py README.md >SHA256SUMS)
install -d -o wwadmin -g wwadmin -m 0700 "$DATA"
if [[ ! -e "$DATA/access-token" ]]; then
    sudo -u wwadmin python3 - "$DATA/access-token" <<'PY'
import os, secrets, sys
path=sys.argv[1]
fd=os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os,"O_NOFOLLOW",0), 0o600)
with os.fdopen(fd,"w",encoding="ascii") as f:
    f.write(secrets.token_hex(32)+"\n")
PY
fi
[[ -f "$DATA/access-token" && ! -L "$DATA/access-token" &&
  "$(stat -c %U "$DATA/access-token")" == wwadmin &&
  "$(stat -c %a "$DATA/access-token")" == 600 ]] || fail "Private token ownership check failed"

if [[ -d "$DEST" ]]; then
    backup="$BACKUPS/$(date -u +%Y%m%dT%H%M%SZ)-$$"
    mv -- "$DEST" "$backup"
fi
mv -- "$stage" "$DEST"
stage=""
chown -R root:root "$DEST"
chmod 0755 "$DEST"
(cd "$DEST" && sha256sum -c SHA256SUMS --quiet) || fail "Installed package verification failed"
finished=1
echo "PASS: G2 package installed with private candidate storage; no service started"
echo "Location: $DEST"
echo "Private data: $DATA"
[[ -z "$backup" ]] || echo "Previous G2 package backup: $backup"
echo "Access via a manually started loopback API and SSH port forwarding only."
