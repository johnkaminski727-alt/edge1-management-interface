#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_ROOT="$REPO_ROOT/deploy/wwcx-admin-electrum/templates"
ADMIN_ROOT="${WWCX_ADMIN_ROOT:-$HOME/public_html/admin}"
BACKUP_ROOT="${WWCX_BACKUP_ROOT:-$HOME/backups/wwcx-admin-electrum}"
MODE="${1:---preflight}"
STAMP="$(date -u +%Y