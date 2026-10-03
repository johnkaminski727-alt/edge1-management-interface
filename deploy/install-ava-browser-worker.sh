#!/bin/sh
set -eu

REPO="/opt/edge1-management-interface"
GATEWAY_ENV="/etc/bigbird-ai-gateway.env"
WORKER_ENV="/etc/wwcx/private-ai-browser-worker.env"
UNIT_SRC="$REPO/deploy/private-ai-browser-worker.service"
UNIT_DST="/etc/systemd/system/private-ai-browser-worker.service"

die() { echo "ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root"
[ -d "$REPO/.git" ] || die "Edge1 repository is unavailable"
[ -f "$UNIT_SRC" ] || die "browser worker unit is unavailable"
[ -f "$REPO/server/private_ai_browser_worker.py" ] || die "browser worker source is unavailable"
[ -f "$REPO/server/ava_agent_controller.py" ] || die "Ava agent controller source is unavailable"
[ -f "$REPO/server/ava_physical_effects.py" ] || die "physical effects policy source is unavailable"
[ -f "$REPO/server/ava_physical_effects_client.py" ] || die "physical effects client source is unavailable"
[ -f "$REPO/server/ava_physical_effects_protocol.py" ] || die "physical effects protocol source is unavailable"
[ -f "$GATEWAY_ENV" ] || die "Ava gateway environment is unavailable"
getent passwd bigbird-ai >/dev/null 2>&1 || die "bigbird-ai service account is unavailable"

grep -q '^BB_RELAY_KEY_ID=' "$GATEWAY_ENV" || die "gateway relay key id is not configured"
grep -q '^BB_RELAY_SECRET=' "$GATEWAY_ENV" || die "gateway relay secret is not configured"

QUEUE_ENV=""
for candidate in   "$WORKER_ENV"   /etc/wwcx/bigbird-ai-poller.env   /etc/bigbird-ai-poller.env
do
  [ -r "$candidate" ] || continue
  if grep -q '^BB_BROWSER_WORKER_KEY_ID=' "$candidate" &&
     grep -q '^BB_BROWSER_WORKER_SECRET=' "$candidate"; then
    QUEUE_ENV="$candidate"
    break
  fi
done

[ -n "$QUEUE_ENV" ] || die "no reusable WW.CX queue worker identity is present; restore/rotate it before activation"

install -d -o root -g bigbird-ai -m 0750 /etc/wwcx
TMP="$(mktemp /etc/wwcx/.private-ai-browser-worker.env.XXXXXX)"
trap 'rm -f "$TMP"' EXIT HUP INT TERM

{
  sed -n -E '/^BB_BROWSER_WORKER_(KEY_ID|SECRET)=/p' "$QUEUE_ENV"
  sed -n -E '/^BB_RELAY_(KEY_ID|SECRET)=/p' "$GATEWAY_ENV"
  printf '%s\n'     'BB_BROWSER_QUEUE_URL=https://ww.cx/api/bigbird-ai-worker.php'     'BB_BROWSER_GATEWAY_URL=http://127.0.0.1:8787/v1/chat'     'BB_BROWSER_WORKER_ID=edge1-private-ai-browser'
} > "$TMP"

for key in   BB_BROWSER_WORKER_KEY_ID   BB_BROWSER_WORKER_SECRET   BB_RELAY_KEY_ID   BB_RELAY_SECRET   BB_BROWSER_QUEUE_URL   BB_BROWSER_GATEWAY_URL   BB_BROWSER_WORKER_ID
do
  [ "$(grep -c "^$key=" "$TMP")" -eq 1 ] || die "worker environment has invalid $key cardinality"
done

chown root:bigbird-ai "$TMP"
chmod 0640 "$TMP"
mv -f "$TMP" "$WORKER_ENV"
trap - EXIT HUP INT TERM

install -o root -g root -m 0644 "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload
systemctl enable private-ai-browser-worker.service >/dev/null
systemctl restart private-ai-browser-worker.service

systemctl is-active --quiet private-ai-browser-worker.service || die "browser worker failed to start"

echo "Ava browser worker installed and active."
echo "Environment: $WORKER_ENV (secret values not displayed)"
echo "Queue: https://ww.cx/api/bigbird-ai-worker.php"
echo "Gateway: http://127.0.0.1:8787/v1/chat"
