#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
DEST=/var/www/edge1-status
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
for f in server/edge1_automation_inventory_exporter.py server/edge1_api_directory_exporter.py src/web/automation-center/index.html src/web/automation-center/app.js src/web/automation-center/styles.css src/web/api-directory/index.html src/web/api-directory/app.js src/web/api-directory/styles.css; do test -s "$ROOT/$f" || { echo "missing $f" >&2; exit 1; }; done
systemd-analyze verify "$ROOT/deploy/automation-api-center/edge1-automation-inventory.service" "$ROOT/deploy/automation-api-center/edge1-automation-inventory.timer" "$ROOT/deploy/automation-api-center/edge1-api-directory.service" "$ROOT/deploy/automation-api-center/edge1-api-directory.timer"
# Use the standard rollback-backed UI publisher so these pages participate in normal interface recovery.
"$ROOT/deploy/operations-center/publish.sh" --apply
for unit in edge1-automation-inventory.service edge1-automation-inventory.timer edge1-api-directory.service edge1-api-directory.timer; do install -m 0644 "$ROOT/deploy/automation-api-center/$unit" "/etc/systemd/system/$unit"; done
systemctl daemon-reload
systemctl enable --now edge1-automation-inventory.timer edge1-api-directory.timer
systemctl start edge1-automation-inventory.service edge1-api-directory.service
# Add only the two new navigation modules; do not overwrite existing navigation customization.
tmp="$(mktemp /tmp/edge1-new-navigation.XXXXXX.json)"; trap 'rm -f "$tmp"' EXIT
cat >"$tmp" <<'JSON'
{"schema_version":1,"contract":"wwcx.edge1-operator-navigation.v1","source_issue":476,"safety":{"navigation_grants_authorization":false,"generic_execution_authorized":false,"production_traffic_authorized":false,"mutations_enabled":false,"unknown_status_is_healthy":false},"modules":[{"id":"automation-center","label":"Automation Center","section":"AI & Automation","sort_order":4,"browser_route":"/edge1-ops/status/automation-center/","candidate_route":"/edge1-ops/status/automation-center/","runtime_route":"/edge1-ops/status/automation-center/","availability":"accepted_live","authorization":"authenticated_read_only","description":"Background bots, scheduled jobs, continuous workers, action boundaries and execution health.","palette":true,"toolbox":true,"evidence_status":"live_generated_inventory","menu_visibility":"primary","dashboard_visibility":true,"enabled":true,"icon":"settings","theme":"inherit"},{"id":"api-directory","label":"API Directory","section":"Tools","sort_order":5,"browser_route":"/edge1-ops/status/api-directory/","candidate_route":"/edge1-ops/status/api-directory/","runtime_route":"/edge1-ops/status/api-directory/","availability":"accepted_live","authorization":"authenticated_read_only","description":"Automatically refreshed directory of live API listeners and source-discovered Edge1 endpoints.","palette":true,"toolbox":true,"evidence_status":"live_and_source_discovery","menu_visibility":"primary","dashboard_visibility":true,"enabled":true,"icon":"link","theme":"inherit"}]}
JSON
/usr/bin/python3 "$ROOT/tools/edge1_operator/navigation_db.py" --database /var/lib/edge1-navigation/navigation.sqlite3 init --bootstrap "$tmp"
/usr/bin/python3 "$ROOT/tools/edge1_operator/navigation_db.py" --database /var/lib/edge1-navigation/navigation.sqlite3 export --output "$DEST/operator-shell/navigation.json"
echo 'Automation Center and API Directory installed.'
