#!/bin/sh
set -eu

MODE=dry-run
EXPECTED_COMMIT=
for arg in "$@"; do
    case "$arg" in
        --dry-run) MODE=dry-run ;;
        --apply) MODE=apply ;;
        --expected-commit=*) EXPECTED_COMMIT=${arg#*=} ;;
        *) echo "usage: $0 [--dry-run|--apply] [--expected-commit=SHA]" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
repo_git() { git -c safe.directory="$REPO_ROOT" -C "$REPO_ROOT" "$@"; }

BOOTSTRAP="$REPO_ROOT/tools/private_library/bootstrap_library_runtime.py"
DATA_ROOT=/var/lib/bigbird-ai-library
DB="$DATA_ROOT/library.sqlite3"
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/private-library-runtime

[ -f "$BOOTSTRAP" ] || { echo "missing bootstrap helper: $BOOTSTRAP" >&2; exit 4; }
python3 -m py_compile "$BOOTSTRAP"

HEAD=$(repo_git rev-parse HEAD 2>/dev/null || printf unknown)
BRANCH=$(repo_git branch --show-current 2>/dev/null || true)
DIRTY=$(repo_git status --porcelain 2>/dev/null || printf unknown)

echo "Big Bird Private Library runtime preflight"
echo "  mode: $MODE"
echo "  repository: $REPO_ROOT"
echo "  branch: ${BRANCH:-detached}"
echo "  commit: $HEAD"
echo "  database: $DB"

if [ "$MODE" != apply ]; then
    echo "Dry run only. No files or services changed."
    exit 0
fi
[ "$(id -u)" -eq 0 ] || { echo "--apply requires root" >&2; exit 3; }
[ -n "$EXPECTED_COMMIT" ] || { echo "--apply requires --expected-commit=SHA" >&2; exit 4; }
case "$EXPECTED_COMMIT" in *[!0-9a-f]*|'') echo "expected commit must be lowercase hexadecimal" >&2; exit 4 ;; esac
[ ${#EXPECTED_COMMIT} -eq 40 ] && [ "$HEAD" = "$EXPECTED_COMMIT" ] || { echo "expected commit mismatch" >&2; exit 4; }
[ -z "$DIRTY" ] || { echo "apply requires a clean checkout" >&2; exit 4; }
if [ -n "$BRANCH" ] && [ "$BRANCH" != main ]; then
    echo "apply requires main or a detached exact-commit checkout" >&2
    exit 4
fi
getent group wwadmin >/dev/null 2>&1 || { echo "wwadmin group is unavailable" >&2; exit 4; }

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$EVIDENCE_ROOT/$STAMP"
install -d -m 0700 "$EVIDENCE"
printf '%s
' "$HEAD" > "$EVIDENCE/repository-commit.txt"

CREATED_DB=0
HAD_DB=0
if [ -f "$DB" ]; then
    HAD_DB=1
    cp -a "$DB" "$EVIDENCE/library.sqlite3.before"
fi

rollback() {
    rc=$?
    trap - EXIT INT TERM
    if [ "$HAD_DB" -eq 1 ]; then
        cp -a "$EVIDENCE/library.sqlite3.before" "$DB"
    elif [ "$CREATED_DB" -eq 1 ]; then
        rm -f "$DB" "$DB-wal" "$DB-shm"
    fi
    exit "$rc"
}
trap rollback EXIT INT TERM

install -d -m 0750 -o root -g wwadmin "$DATA_ROOT"
if [ ! -f "$DB" ]; then
    python3 "$BOOTSTRAP" --db "$DB" --seed-bootstrap
    CREATED_DB=1
else
    python3 "$BOOTSTRAP" --db "$DB"
fi
chown root:wwadmin "$DB"
chmod 0640 "$DB"

python3 - "$DB" <<'PY' > "$EVIDENCE/database-validation.txt"
import sqlite3, sys
db=sys.argv[1]
con=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
try:
    integrity=con.execute("PRAGMA integrity_check").fetchone()[0]
    chunks=con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    fts=con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    print("integrity=" + str(integrity))
    print("chunks=" + str(chunks))
    print("fts=" + str(fts))
    if integrity != "ok" or chunks != fts:
        raise SystemExit(1)
finally:
    con.close()
PY
sha256sum "$DB" > "$EVIDENCE/database.sha256"
trap - EXIT INT TERM
echo "Big Bird Private Library runtime ready: $DB"
echo "Evidence: $EVIDENCE"
