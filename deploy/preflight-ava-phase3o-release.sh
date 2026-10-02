#!/bin/sh
set -eu

EXPECTED_COMMIT=
for arg in "$@"; do
    case "$arg" in
        --expected-commit=*) EXPECTED_COMMIT=${arg#*=} ;;
        *) echo "usage: $0 --expected-commit=SHA" >&2; exit 2 ;;
    esac
done

[ -n "$EXPECTED_COMMIT" ] || { echo "--expected-commit=SHA is required" >&2; exit 2; }
case "$EXPECTED_COMMIT" in *[!0-9a-f]*|'') echo "expected commit must be lowercase hexadecimal" >&2; exit 2 ;; esac
[ ${#EXPECTED_COMMIT} -eq 40 ] || { echo "expected commit must be 40 hex characters" >&2; exit 2; }

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
repo_git() { git -c safe.directory="$REPO_ROOT" -C "$REPO_ROOT" "$@"; }

HEAD=$(repo_git rev-parse HEAD)
BRANCH=$(repo_git branch --show-current || true)
DIRTY=$(repo_git status --porcelain)

echo "=== AVA PHASE 3O DETACHED RELEASE PREFLIGHT ==="
echo "repository: $REPO_ROOT"
echo "branch: ${BRANCH:-detached}"
echo "head: $HEAD"
echo "expected: $EXPECTED_COMMIT"

[ "$HEAD" = "$EXPECTED_COMMIT" ] || { echo "STOP: expected commit mismatch" >&2; exit 4; }
[ -z "$DIRTY" ] || { echo "STOP: release worktree is not clean" >&2; exit 4; }
[ -z "$BRANCH" ] || { echo "STOP: preflight requires a detached exact-commit worktree" >&2; exit 4; }

required_files="
services/bigbird-ai-gateway/app/__init__.py
services/bigbird-ai-gateway/app/library_engine.py
services/bigbird-ai-gateway/app/main.py
server/ava_agent_controller.py
server/ava_contacts_gateway.py
server/phone_intelligence_gateway.py
server/private_ai_browser_worker.py
server/private_library_search_server.py
tools/ava_gateway_signed_acceptance.py
tools/private_library/bootstrap_library_runtime.py
deploy/install-ava-readonly-gateway.sh
deploy/install-ava-browser-worker.sh
deploy/install-bigbird-private-library-runtime.sh
deploy/systemd/bigbird-ai-gateway.service
deploy/private-ai-browser-worker.service
"

echo
echo "=== REQUIRED SOURCE INVENTORY ==="
printf '%s\n' "$required_files" | while IFS= read -r relative; do
    [ -n "$relative" ] || continue
    [ -f "$REPO_ROOT/$relative" ] || { echo "MISSING: $relative" >&2; exit 5; }
    echo "OK: $relative"
done

echo
echo "=== PYTHON COMPILE ==="
python3 -m py_compile     "$REPO_ROOT/services/bigbird-ai-gateway/app/library_engine.py"     "$REPO_ROOT/services/bigbird-ai-gateway/app/main.py"     "$REPO_ROOT/server/ava_agent_controller.py"     "$REPO_ROOT/server/ava_contacts_gateway.py"     "$REPO_ROOT/server/phone_intelligence_gateway.py"     "$REPO_ROOT/server/private_ai_browser_worker.py"     "$REPO_ROOT/server/private_library_search_server.py"     "$REPO_ROOT/tools/ava_gateway_signed_acceptance.py"     "$REPO_ROOT/tools/private_library/bootstrap_library_runtime.py"
echo "PASS: Python compile"

echo
echo "=== INSTALLER SYNTAX ==="
sh -n "$REPO_ROOT/deploy/install-ava-readonly-gateway.sh"
sh -n "$REPO_ROOT/deploy/install-ava-browser-worker.sh"
sh -n "$REPO_ROOT/deploy/install-bigbird-private-library-runtime.sh"
echo "PASS: installer syntax"

echo
echo "=== SYSTEMD STATIC VERIFY ==="
if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify         "$REPO_ROOT/deploy/systemd/bigbird-ai-gateway.service"         "$REPO_ROOT/deploy/private-ai-browser-worker.service"
    echo "PASS: systemd unit verification"
else
    echo "NOTICE: systemd-analyze unavailable; static unit verification skipped"
fi

echo
echo "=== COMMISSIONING DRY RUNS ==="
"$REPO_ROOT/deploy/install-bigbird-private-library-runtime.sh" --dry-run
"$REPO_ROOT/deploy/install-ava-readonly-gateway.sh" --dry-run
"$REPO_ROOT/deploy/install-ava-browser-worker.sh" --dry-run
echo "PASS: dry-run commissioning"

echo
echo "=== FOCUSED UNIT TESTS ==="
(
    cd "$REPO_ROOT"
    python3 -m unittest         tests.test_ava_agent_controller         tests.test_ava_contacts_gateway         tests.test_ava_readonly_gateway         tests.test_bigbird_private_library_engine         tests.test_ava_phase3o_commissioning
)
echo "PASS: focused unit tests"

echo
echo "=== LIVE STATE — READ ONLY ==="
for service in     bigbird-ai-gateway.service     private-ai-browser-worker.service     edge1-operations-api.service     edge1-private-library-search.service
do
    if command -v systemctl >/dev/null 2>&1; then
        active=$(systemctl is-active "$service" 2>/dev/null || true)
        enabled=$(systemctl is-enabled "$service" 2>/dev/null || true)
        printf '%-42s active=%-12s enabled=%s\n' "$service" "$active" "$enabled"
    fi
done

for pointer in     /opt/bigbird-ai-gateway/current     /opt/wwcx-private-ai-browser-worker/current
do
    if [ -L "$pointer" ]; then
        echo "$pointer -> $(readlink -f "$pointer")"
    elif [ -e "$pointer" ]; then
        echo "$pointer exists but is not a symlink"
    else
        echo "$pointer absent"
    fi
done

echo
echo "=== LIVE LISTENERS — READ ONLY ==="
if command -v ss >/dev/null 2>&1; then
    ss -ltn | grep -E '127\.0\.0\.1:(8787|8097|8769|8770)[[:space:]]' || true
fi

echo
echo "PASS: Phase 3O detached release preflight completed."
echo "No files, services, runtime pointers, credentials, routes, or browser state were changed."
