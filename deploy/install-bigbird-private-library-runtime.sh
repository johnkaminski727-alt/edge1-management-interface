#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_ROOT="/opt/bigbird-ai-gateway"
APP_ROOT="$RUNTIME_ROOT/app"
DATA_ROOT="/var/lib/bigbird-ai-library"
DB="$DATA_ROOT/library.sqlite3"

if [ "${EUID}" -ne 0 ]; then
  echo "install-bigbird-private-library-runtime.sh must run as root" >&2
  exit 1
fi

test -f "$ROOT/services/bigbird-ai-gateway/app/library_engine.py"
test -f "$ROOT/tools/private_library/bootstrap_library_runtime.py"

install -d -m 0755 "$RUNTIME_ROOT" "$APP_ROOT"
install -m 0644 "$ROOT/services/bigbird-ai-gateway/app/__init__.py" "$APP_ROOT/__init__.py"
install -m 0644 "$ROOT/services/bigbird-ai-gateway/app/library_engine.py" "$APP_ROOT/library_engine.py"

install -d -m 0750 "$DATA_ROOT"
/usr/bin/python3 "$ROOT/tools/private_library/bootstrap_library_runtime.py" --db "$DB" --seed-bootstrap

chown -R root:root "$RUNTIME_ROOT"
chmod 0755 "$RUNTIME_ROOT" "$APP_ROOT"
chmod 0644 "$APP_ROOT/__init__.py" "$APP_ROOT/library_engine.py"

chown root:wwadmin "$DATA_ROOT" "$DB"
chmod 0750 "$DATA_ROOT"
chmod 0640 "$DB"

echo "Installed Big Bird Private Library runtime:"
echo "  engine: $APP_ROOT/library_engine.py"
echo "  db:     $DB"
