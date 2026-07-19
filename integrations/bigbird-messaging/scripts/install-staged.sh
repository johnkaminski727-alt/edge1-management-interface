#!/bin/sh
set -eu

SOURCE_ROOT="${SOURCE_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)}"
BIGBIRD_ROOT="${BIGBIRD_ROOT:-/opt/bigbird-ai-gateway}"
STAGE_ROOT="${STAGE_ROOT:-$BIGBIRD_ROOT/.staging/wwcx-messaging}"

[ -d "$BIGBIRD_ROOT" ] || {
  printf 'BigBird root not found: %s\n' "$BIGBIRD_ROOT" >&2
  exit 1
}

umask 077
rm -rf "$STAGE_ROOT"
mkdir -p "$STAGE_ROOT/integrations/bigbird_messaging" "$STAGE_ROOT/config"
cp "$SOURCE_ROOT/integrations/bigbird_messaging/__init__.py" "$STAGE_ROOT/integrations/bigbird_messaging/"
cp "$SOURCE_ROOT/integrations/bigbird_messaging/client.py" "$STAGE_ROOT/integrations/bigbird_messaging/"
cp "$SOURCE_ROOT/integrations/bigbird_messaging/tools.py" "$STAGE_ROOT/integrations/bigbird_messaging/"
cp "$SOURCE_ROOT/integrations/bigbird-messaging/tool-manifest.json" "$STAGE_ROOT/"
cp "$SOURCE_ROOT/integrations/bigbird-messaging/contract/management-api-v1.json" "$STAGE_ROOT/"
cp "$SOURCE_ROOT/integrations/bigbird-messaging/config/bigbird-messaging.env.example" "$STAGE_ROOT/config/"
python3 -m compileall -q "$STAGE_ROOT/integrations/bigbird_messaging"

printf 'Staged BigBird messaging adapter at %s\n' "$STAGE_ROOT"
printf 'No live files, credentials, registry entries, or services were changed.\n'
