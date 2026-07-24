#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/edge1-management-interface"

echo "=== OPERATIONS CENTER VALIDATION ==="

cd "$ROOT"

echo
echo "[Portal]"
test -f /var/www/edge1-status/index.html
echo "OK"

echo
echo "[Artifacts]"

for f in \
operations-health.json \
operations-timeline.json \
operations-changes.json \
daily-summary.json \
operations-automation.json \
operations-correlation.json \
operations-version.json
do
    test -f "/var/www/edge1-status/$f"
    echo "OK $f"
done

echo
echo "[Timers]"

for t in \
wwcx-operations-health.timer \
wwcx-operations-timeline.timer \
wwcx-operations-summary.timer \
wwcx-operations-automation-health.timer \
wwcx-operations-changes.timer \
wwcx-operations-correlation.timer \
wwcx-operations-report.timer \
wwcx-operations-version.timer
do
    systemctl is-active --quiet "$t"
    echo "OK $t"
done

echo
echo "[Git]"

git status --short --branch

echo
echo "[HTTP]"

curl -fsS http://127.0.0.1/edge1-status/ >/dev/null

echo "OK portal reachable"

echo
echo "=== COMPLETE ==="
