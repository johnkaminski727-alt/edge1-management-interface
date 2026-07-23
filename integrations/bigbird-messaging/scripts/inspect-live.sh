#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/edge1-management-interface}"
BIGBIRD_ROOT="${BIGBIRD_ROOT:-/opt/bigbird-ai-gateway}"
BIGBIRD_URL="${BIGBIRD_URL:-http://127.0.0.1:8787}"
BIGBIRD_SERVICE="${BIGBIRD_SERVICE:-bigbird-ai-gateway.service}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE="${EVIDENCE_DIR:-/tmp/wwcx-messaging-live-inspection-$STAMP}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

command -v git >/dev/null || fail "git is required"
command -v curl >/dev/null || fail "curl is required"
command -v python3 >/dev/null || fail "python3 is required"
command -v systemctl >/dev/null || fail "systemctl is required"

[ "$(hostname -f)" = "edge1.ww.cx" ] || fail "host mismatch: expected edge1.ww.cx"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found at $REPO_ROOT"
[ -d "$BIGBIRD_ROOT" ] || fail "BigBird root not found at $BIGBIRD_ROOT"

umask 077
mkdir -p "$EVIDENCE"

printf '%s\n' "$(hostname -f)" > "$EVIDENCE/hostname.txt"
id > "$EVIDENCE/identity.txt"
date -u --iso-8601=seconds > "$EVIDENCE/started-at.txt"

(
  cd "$REPO_ROOT"
  git status --short
) > "$EVIDENCE/edge1-git-status.txt"
(
  cd "$REPO_ROOT"
  git rev-parse HEAD
) > "$EVIDENCE/edge1-head.txt"

systemctl status "$BIGBIRD_SERVICE" --no-pager > "$EVIDENCE/bigbird-status.txt" 2>&1 || true
journalctl -u "$BIGBIRD_SERVICE" -n 200 --no-pager > "$EVIDENCE/bigbird-journal.txt" 2>&1 || true
ss -lntup > "$EVIDENCE/listeners.txt"

if [ -d "$BIGBIRD_ROOT/app" ]; then
  find "$BIGBIRD_ROOT/app" \
    -path '*/__pycache__' -prune -o \
    -maxdepth 2 -type f -printf '%M %u:%g %p\n' 2>/dev/null \
    | sort > "$EVIDENCE/bigbird-app-files.txt" || true
else
  printf 'BigBird app directory not found: %s/app\n' "$BIGBIRD_ROOT" \
    > "$EVIDENCE/bigbird-app-files.txt"
fi

for endpoint in health tools openapi.json; do
  case "$endpoint" in
    health) path="/health" ;;
    tools) path="/v1/tools" ;;
    openapi.json) path="/openapi.json" ;;
  esac
  curl -fsS --max-time 10 "$BIGBIRD_URL$path" > "$EVIDENCE/$endpoint" || true
done

python3 - "$EVIDENCE" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
for name in ("health", "tools", "openapi.json"):
    path = root / name
    if not path.exists() or not path.stat().st_size:
        continue
    try:
        json.loads(path.read_text())
    except Exception as exc:
        raise SystemExit(f"{name} is not valid JSON: {exc}")
PY

if [ -f /etc/bigbird-ai-gateway.env ]; then
  sed -n 's/^\(WWCX_[A-Z0-9_]*\|BIGBIRD_[A-Z0-9_]*\)=.*/\1=<redacted>/p' \
    /etc/bigbird-ai-gateway.env > "$EVIDENCE/bigbird-env-redacted.txt" || true
fi

systemctl list-units --type=service --all --no-pager \
  | grep -Ei 'wwcx|messag|bigbird' > "$EVIDENCE/related-services.txt" || true

find /etc/systemd/system /lib/systemd/system -maxdepth 1 -type f \
  \( -iname '*wwcx*' -o -iname '*messag*' -o -iname '*bigbird*' \) \
  -printf '%p\n' 2>/dev/null | sort > "$EVIDENCE/related-units.txt" || true

date -u --iso-8601=seconds > "$EVIDENCE/completed-at.txt"

printf 'Inspection complete. Evidence: %s\n' "$EVIDENCE"
printf 'No files, credentials, registry entries, listeners, or services were changed.\n'
printf 'Do not paste secret-bearing files. Share only the evidence path and sanitized outputs.\n'
