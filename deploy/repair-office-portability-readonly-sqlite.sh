#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
repo_git() { git -c safe.directory="$ROOT" -C "$ROOT" "$@"; }
MODE=dry-run
EXPECTED_COMMIT=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) MODE=dry-run ;;
        --apply) MODE=apply ;;
        --expected-commit=*) EXPECTED_COMMIT="${arg#*=}" ;;
        *) echo "usage: $0 [--dry-run|--apply] [--expected-commit=SHA]" >&2; exit 2 ;;
    esac
done

AVA_SERVICE=wwcx-ava-office.service
PORT_SERVICE=wwcx-number-portability.service
AVA_DB=/var/lib/wwcx-ava-office-manager/office-manager.sqlite3
PORT_DB=/var/lib/wwcx-portability/portability.sqlite3
AVA_SUMMARY=http://127.0.0.1:8116/api/ava-office/summary
PORT_SUMMARY=http://127.0.0.1:8117/api/portability/summary
BRIDGE="$ROOT/deploy/activate-office-portability-operations-bridge.sh"
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/office-portability-sqlite-repair

HEAD="$(repo_git rev-parse HEAD)"
BRANCH="$(repo_git branch --show-current || true)"
DIRTY="$(repo_git status --porcelain)"

echo "Office/Portability SQLite read-only compatibility repair"
echo "  mode: $MODE"
echo "  branch: ${BRANCH:-detached}"
echo "  commit: $HEAD"

if [ "$MODE" = dry-run ]; then
    echo "Dry run only. No database, service, or collector changes made."
    exit 0
fi

[ "$(id -u)" -eq 0 ] || { echo "--apply requires root" >&2; exit 3; }
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "--apply requires --expected-commit=SHA" >&2; exit 4; }
[ "$HEAD" = "$EXPECTED_COMMIT" ] || { echo "expected commit mismatch" >&2; exit 4; }
[ -z "$DIRTY" ] || { echo "apply requires clean working tree" >&2; exit 4; }
if [ -n "$BRANCH" ] && [ "$BRANCH" != main ]; then
    echo "apply requires main or a detached exact-commit checkout" >&2
    exit 4
fi
[ -f "$BRIDGE" ] || { echo "missing bridge activation script" >&2; exit 4; }
[ -f "$AVA_DB" ] || { echo "Ava Office database missing" >&2; exit 4; }
[ -f "$PORT_DB" ] || { echo "Number Portability database missing" >&2; exit 4; }

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE="$EVIDENCE_ROOT/$STAMP"
BACKUP="$EVIDENCE/backups"
install -d -m 0700 "$EVIDENCE" "$BACKUP"
printf '%s\n' "$HEAD" > "$EVIDENCE/repository-commit.txt"

systemctl is-active --quiet "$AVA_SERVICE"
systemctl is-active --quiet "$PORT_SERVICE"

restore_databases() {
    set +e
    systemctl stop "$AVA_SERVICE" "$PORT_SERVICE" >/dev/null 2>&1 || true
    for name in ava portability; do
        case "$name" in
            ava) live="$AVA_DB"; backup="$BACKUP/ava.sqlite3" ;;
            portability) live="$PORT_DB"; backup="$BACKUP/portability.sqlite3" ;;
        esac
        if [ -f "$backup" ]; then
            cp -a "$backup" "$live"
            chown wwadmin:wwadmin "$live"
            chmod 0600 "$live"
            rm -f "$live-wal" "$live-shm"
        fi
    done
    systemctl start "$AVA_SERVICE" "$PORT_SERVICE" >/dev/null 2>&1 || true
}

trap 'rc=$?; echo "SQLite compatibility repair failed; restoring database backups." >&2; restore_databases; exit "$rc"' ERR INT TERM

printf '=== BACKUP AND JOURNAL MIGRATION ===\n'
systemctl stop "$AVA_SERVICE" "$PORT_SERVICE"

python3 - "$AVA_DB" "$BACKUP/ava.sqlite3" work_items action_proposals standing_instructions <<'PY'
import json, sqlite3, sys
source, backup, *required = sys.argv[1:]
src = sqlite3.connect(source, timeout=10)
dst = sqlite3.connect(backup)
src.backup(dst)
dst.close()
before = str(src.execute('PRAGMA journal_mode').fetchone()[0]).lower()
try:
    src.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
except sqlite3.DatabaseError:
    pass
after = str(src.execute('PRAGMA journal_mode=DELETE').fetchone()[0]).lower()
integrity = str(src.execute('PRAGMA integrity_check').fetchone()[0]).lower()
tables = {row[0] for row in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
src.close()
if after != 'delete':
    raise SystemExit('Ava database did not enter DELETE journal mode')
if integrity != 'ok':
    raise SystemExit('Ava database integrity check failed')
missing = sorted(set(required) - tables)
if missing:
    raise SystemExit('Ava database schema incomplete: ' + ','.join(missing))
print(json.dumps({'database':'ava_office','journal_before':before,'journal_after':after,'integrity':'ok'}, sort_keys=True))
PY

python3 - "$PORT_DB" "$BACKUP/portability.sqlite3" port_cases port_numbers port_documents <<'PY'
import json, sqlite3, sys
source, backup, *required = sys.argv[1:]
src = sqlite3.connect(source, timeout=10)
dst = sqlite3.connect(backup)
src.backup(dst)
dst.close()
before = str(src.execute('PRAGMA journal_mode').fetchone()[0]).lower()
try:
    src.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
except sqlite3.DatabaseError:
    pass
after = str(src.execute('PRAGMA journal_mode=DELETE').fetchone()[0]).lower()
integrity = str(src.execute('PRAGMA integrity_check').fetchone()[0]).lower()
tables = {row[0] for row in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
src.close()
if after != 'delete':
    raise SystemExit('Portability database did not enter DELETE journal mode')
if integrity != 'ok':
    raise SystemExit('Portability database integrity check failed')
missing = sorted(set(required) - tables)
if missing:
    raise SystemExit('Portability database schema incomplete: ' + ','.join(missing))
print(json.dumps({'database':'number_portability','journal_before':before,'journal_after':after,'integrity':'ok'}, sort_keys=True))
PY

chown wwadmin:wwadmin "$AVA_DB" "$PORT_DB"
chmod 0600 "$AVA_DB" "$PORT_DB"
[ ! -e "$AVA_DB-wal" ] && [ ! -e "$AVA_DB-shm" ]
[ ! -e "$PORT_DB-wal" ] && [ ! -e "$PORT_DB-shm" ]

systemctl start "$AVA_SERVICE" "$PORT_SERVICE"
systemctl is-active --quiet "$AVA_SERVICE"
systemctl is-active --quiet "$PORT_SERVICE"

printf '=== VERIFY READ-ONLY SUMMARY ROUTES ===\n'
curl --fail --silent --show-error "$AVA_SUMMARY" > "$EVIDENCE/ava-summary.json"
curl --fail --silent --show-error "$PORT_SUMMARY" > "$EVIDENCE/portability-summary.json"
python3 - "$EVIDENCE/ava-summary.json" "$EVIDENCE/portability-summary.json" <<'PY'
import json, pathlib, sys
ava = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
port = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
assert ava.get('mode') == 'read-only'
assert isinstance(ava.get('work_items'), dict)
assert isinstance(ava.get('actions'), dict)
assert isinstance(ava.get('standing_instructions'), int)
assert port.get('mode') == 'read-only'
assert isinstance(port.get('cases'), dict)
assert isinstance(port.get('numbers'), int)
assert isinstance(port.get('documents'), int)
assert port.get('submission_authorized') is False
assert port.get('cutover_authorized') is False
print(json.dumps({'ava_summary':'ok','portability_summary':'ok','submission_authorized':False,'cutover_authorized':False}, sort_keys=True))
PY

trap - ERR INT TERM
printf 'sqlite_repair=accepted\nrollback_required=false\n' > "$EVIDENCE/result.txt"

printf '=== REFRESH SIGNED OPERATIONS BRIDGE ===\n'
bash "$BRIDGE" --apply --expected-commit="$EXPECTED_COMMIT"

printf '=== FINAL HEALTH ===\n'
systemctl is-active "$AVA_SERVICE"
systemctl is-active "$PORT_SERVICE"
curl --fail --silent --show-error http://127.0.0.1:8116/healthz; echo
curl --fail --silent --show-error http://127.0.0.1:8117/healthz; echo

echo "Office/Portability SQLite repair completed. Evidence: $EVIDENCE"
