#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
install -m 0755 "$ROOT/server/edge1_email_gateway_status_exporter.py" /usr/local/sbin/edge1-email-gateway-status-export
install -m 0644 "$ROOT/deploy/systemd/edge1-email-gateway-status-export.service" /etc/systemd/system/edge1-email-gateway-status-export.service
install -m 0644 "$ROOT/deploy/systemd/edge1-email-gateway-status-export.timer" /etc/systemd/system/edge1-email-gateway-status-export.timer
systemctl daemon-reload
systemctl enable --now edge1-email-gateway-status-export.timer
systemctl start edge1-email-gateway-status-export.service
