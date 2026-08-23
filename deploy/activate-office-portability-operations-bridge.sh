#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
EXPECTED_COMMIT=""
MODE=dry-run
for arg in "$@"; do
    case "$arg" in
        --dry-run) MODE=dry-run ;;
        --apply) MODE=apply ;;
        --expected-commit=*) EXPECTED_COMMIT="${arg#*=}" ;;
        *) echo "usage: $0 [--dry-run|--apply] [--expected-commit=SHA]" >&2; exit 2 ;;
    esac
done

COLLECTOR_SOURCE="$ROOT/server/bigbird_ops_collect.py"
SUMMARY_SOURCE="$ROOT/server/office_portability_bridge_summary.py"
COLLECTOR_LIVE=/usr/local/libexec/bigbird-ops-collect.py
SUMMARY_LIVE=/usr/local/libexec/office_portability_bridge_summary.py
PUSH_SERVICE=bigbird-ops-push.service
SNAPSHOT=/var/lib/bigbird/operations-center/latest.json
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/office-portability-bridge

python3 -m py_compile "$COLLECTOR_SOURCE" "$SUMMARY_SOURCE"
HEAD="$(git -C "$ROOT" rev-parse HEAD)"
BRANCH="$(git -C "$ROOT" branch --show-current)"
DIRTY="$(git -C "$ROOT" status --porcelain)"

echo "Office/Portability signed snapshot bridge preflight"
echo "  mode: $MODE"
echo "  branch: $BRANCH"
echo "  commit: $HEAD"

if [ "$MODE" = dry-run ]; then
    echo "Dry run only. No runtime files or services changed."
    exit 0
fi
[ "$(id -u)" -eq 0 ] || { echo "--apply requires root" >&2; exit 3; }
[ -n "$EXPECTED_COMMIT" ] || { echo "--apply requires --expected-commit=SHA" >&2; exit 4; }
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid expected commit" >&2; exit 4; }
[ "$HEAD" = "$EXPECTED_COMMIT" ] || { echo "expected commit mismatch" >&2; exit 4; }
[ "$BRANCH" = main ] || { echo "apply requires main" >&2; exit 4; }
[ -z "$DIRTY" ] || { echo "apply requires clean working tree" >&2; exit 4; }

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE="$EVIDENCE_ROOT/$STAMP"
BACKUP="$EVIDENCE/backups"
install -d -m 0700 "$EVIDENCE" "$BACKUP"
printf '%s\n' "$HEAD" > "$EVIDENCE/repository-commit.txt"

HAD_COLLECTOR=0
HAD_SUMMARY=0
[ -f "$COLLECTOR_LIVE" ] && { HAD_COLLECTOR=1; cp -a "$COLLECTOR_LIVE" "$BACKUP/collector.before"; }
[ -f "$SUMMARY_LIVE" ] && { HAD_SUMMARY=1; cp -a "$SUMMARY_LIVE" "$BACKUP/summary.before"; }

rollback() {
    rc=$?
    trap - ERR INT TERM
    set +e
    if [ "$HAD_COLLECTOR" -eq 1 ]; then install -D -o root -g root -m 0700 "$BACKUP/collector.before" "$COLLECTOR_LIVE"; else rm -f "$COLLECTOR_LIVE"; fi
    if [ "$HAD_SUMMARY" -eq 1 ]; then install -D -o root -g root -m 0600 "$BACKUP/summary.before" "$SUMMARY_LIVE"; else rm -f "$SUMMARY_LIVE"; fi
    systemctl start "$PUSH_SERVICE" >/dev/null 2>&1 || true
    printf 'accepted=false\nrolled_back=true\nexit_code=%s\n' "$rc" > "$EVIDENCE/result.txt"
    exit "$rc"
}
trap rollback ERR INT TERM

install -D -o root -g root -m 0700 "$COLLECTOR_SOURCE" "$COLLECTOR_LIVE"
install -D -o root -g root -m 0600 "$SUMMARY_SOURCE" "$SUMMARY_LIVE"
sha256sum "$COLLECTOR_LIVE" "$SUMMARY_LIVE" > "$EVIDENCE/runtime.sha256"

systemctl start "$PUSH_SERVICE"
[ "$(systemctl show "$PUSH_SERVICE" --property=Result --value)" = success ]
[ "$(systemctl show "$PUSH_SERVICE" --property=ExecMainStatus --value)" = 0 ]
[ -f "$SNAPSHOT" ]

python3 - "$SNAPSHOT" "$EVIDENCE/acceptance.json" <<'PY'
import json
import pathlib
import sys

snapshot = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
data = json.loads(snapshot.read_text(encoding='utf-8'))
assert data['format'] == 'project-big-bird-operations-center-v1'
assert data['project_version'] == '4.0.5'
assert data['read_only'] is True
assert data['provisioning_locked'] is True
assert data['authoritative_dns_editing_locked'] is True
assert isinstance(data['ava_office'], dict)
assert isinstance(data['number_portability'], dict)
privacy = data['office_services_privacy']
for key in (
    'record_level_content_included',
    'telephone_numbers_included',
    'transcripts_or_audio_included',
    'document_references_included',
    'credentials_included',
):
    assert privacy[key] is False
assert data['ava_office'].get('execution_enabled') is False
assert data['number_portability'].get('submission_authorized') is False
assert data['number_portability'].get('cutover_authorized') is False
summary = {
    'ok': True,
    'ava_available': bool(data['ava_office'].get('available')),
    'portability_available': bool(data['number_portability'].get('available')),
    'privacy': privacy,
}
out.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, sort_keys=True))
PY

printf 'accepted=true\nrolled_back=false\nread_only=true\n' > "$EVIDENCE/result.txt"
trap - ERR INT TERM
echo "Office/Portability bridge activation passed. Evidence: $EVIDENCE"
