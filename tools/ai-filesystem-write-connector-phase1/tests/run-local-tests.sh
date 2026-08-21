#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/etc" "$TMP/target/docs" "$TMP/state" "$TMP/log"

sed \
  -e "s#/var/lib/bigbird-fsctl/staging#$TMP/state/staging#g" \
  -e "s#/var/lib/bigbird-fsctl/backups#$TMP/state/backups#g" \
  -e "s#/var/log/bigbird-fsctl/audit.jsonl#$TMP/log/audit.jsonl#g" \
  -e "s#/opt/edge1-management-interface/docs#$TMP/target/docs#g" \
  "$ROOT/etc/bigbird-fsctl-policy.json" > "$TMP/etc/policy.json"

export BIGBIRD_FSCTL_POLICY="$TMP/etc/policy.json"
export BIGBIRD_FSCTL_ALLOW_NONROOT=1

python3 "$ROOT/sbin/bigbird-fsctl" init >/tmp/bigbird-fsctl-test-init.json

cat > "$TMP/proposed.md" <<'EOF'
# Local Phase 1 Test

This is a local staged write test.
EOF

stage_id="$(python3 "$ROOT/sbin/bigbird-fsctl" stage \
  --source "$TMP/proposed.md" \
  --target "$TMP/target/docs/local-test.md" \
  --actor test \
  --reason "local test" | python3 -c 'import json,sys; print(json.load(sys.stdin)["stage_id"])')"

if python3 "$ROOT/sbin/bigbird-fsctl" apply "$stage_id" >/tmp/bigbird-fsctl-unapproved.out 2>&1; then
  echo "apply succeeded without approval" >&2
  exit 1
fi

python3 "$ROOT/sbin/bigbird-fsctl" inspect "$stage_id" >/tmp/bigbird-fsctl-inspect.json
python3 "$ROOT/sbin/bigbird-fsctl" diff "$stage_id" >/tmp/bigbird-fsctl-diff.txt
python3 "$ROOT/sbin/bigbird-fsctl" approve --by test "$stage_id" >/tmp/bigbird-fsctl-approve.json
python3 "$ROOT/sbin/bigbird-fsctl" apply "$stage_id" >/tmp/bigbird-fsctl-apply.json
test -f "$TMP/target/docs/local-test.md"
grep -q "Local Phase 1 Test" "$TMP/target/docs/local-test.md"
python3 "$ROOT/sbin/bigbird-fsctl" audit --limit 20 | grep -q "fs.apply_succeeded"
python3 "$ROOT/sbin/bigbird-fsctl" rollback --by test "$stage_id" >/tmp/bigbird-fsctl-rollback.json
test ! -f "$TMP/target/docs/local-test.md"

printf '%s\n' 'original target content' > "$TMP/target/docs/drift-test.md"
printf '%s\n' 'proposed replacement content' > "$TMP/drift-proposed.md"
drift_stage_id="$(python3 "$ROOT/sbin/bigbird-fsctl" stage \
  --source "$TMP/drift-proposed.md" \
  --target "$TMP/target/docs/drift-test.md" \
  --actor test \
  --reason "drift precondition test" | python3 -c 'import json,sys; print(json.load(sys.stdin)["stage_id"])')"
python3 "$ROOT/sbin/bigbird-fsctl" approve --by test "$drift_stage_id" >/tmp/bigbird-fsctl-drift-approve.json
printf '%s\n' 'external concurrent change' > "$TMP/target/docs/drift-test.md"
if python3 "$ROOT/sbin/bigbird-fsctl" apply "$drift_stage_id" >/tmp/bigbird-fsctl-drift-apply.out 2>&1; then
  echo "apply succeeded despite target drift" >&2
  exit 1
fi
grep -q "target precondition failed" /tmp/bigbird-fsctl-drift-apply.out
grep -q "external concurrent change" "$TMP/target/docs/drift-test.md"
python3 "$ROOT/sbin/bigbird-fsctl" audit --limit 50 | grep -q "fs.apply_precondition_failed"

if python3 "$ROOT/sbin/bigbird-fsctl" stage \
  --source "$TMP/proposed.md" \
  --target "$TMP/target/not-docs/bad.md" \
  --actor test \
  --reason "outside root" >/tmp/bigbird-fsctl-bad.out 2>&1; then
  echo "outside-root stage unexpectedly succeeded" >&2
  exit 1
fi

echo "Phase 1 local tests passed."
