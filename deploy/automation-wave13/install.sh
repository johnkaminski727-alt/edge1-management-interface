#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
test -s "$ROOT/tools/automation/reply_suggestion_bot.py"
test -s /etc/wwcx/mail-room-ava.env
systemd-analyze verify "$ROOT/deploy/automation-wave13/edge1-reply-suggestions.service" "$ROOT/deploy/automation-wave13/edge1-reply-suggestions.timer"
install -d -m 0700 /var/lib/edge1-reply-suggestions
install -d -m 0755 /var/www/edge1-status/reply-suggestions
install -m 0644 "$ROOT/deploy/automation-wave13/edge1-reply-suggestions.service" /etc/systemd/system/edge1-reply-suggestions.service
install -m 0644 "$ROOT/deploy/automation-wave13/edge1-reply-suggestions.timer" /etc/systemd/system/edge1-reply-suggestions.timer
systemctl daemon-reload
systemctl enable --now edge1-reply-suggestions.timer
systemctl start edge1-reply-suggestions.service
echo 'Automation wave 13 reply suggestions installed.'
