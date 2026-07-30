#!/usr/bin/env bash
set -Eeuo pipefail
REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
: "${EDGE1_AUTH_USER_FILE:?set EDGE1_AUTH_USER_FILE to an existing approved root-owned Apache password file}"
: "${EDGE1_AUTH_ACCEPTANCE_FILE:?set EDGE1_AUTH_ACCEPTANCE_FILE to a root-owned mode-0600 acceptance JSON file}"
export EDGE1_MANAGEMENT_ROOT="$REPO_ROOT" EDGE1_AUTH_USER_FILE EDGE1_AUTH_ACCEPTANCE_FILE
bash "$REPO_ROOT/tools/security/edge1-security-completion-preflight.sh"
bash "$REPO_ROOT/deploy/activate-suricata-protected-retention.sh"
bash "$REPO_ROOT/deploy/stage-edge1-public-boundary.sh"
bash "$REPO_ROOT/deploy/cutover-edge1-public-boundary.sh"
