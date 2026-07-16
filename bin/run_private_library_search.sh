#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
port="${1:-8091}"
env_file="$repo_root/config/private-library-search.env"

if [[ -f "$env_file" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
fi

cd "$repo_root"
exec python3 server/private_library_search_server.py --host 127.0.0.1 --port "$port"

