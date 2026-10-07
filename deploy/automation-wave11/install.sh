#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
python3 -m unittest -v tests.test_contact_enrichment_research tests.test_unified_contacts_maintenance_bot tests.test_unified_contacts_maintenance_review
systemd-analyze verify "$ROOT/deploy/automation-wave11/edge1-contact-enrichment-research.service" "$ROOT/deploy/automation-wave11/edge1-contact-enrichment-research.timer"
install -d -m 0755 /var/www/edge1-status/contact-enrichment-research
install -m 0644 "$ROOT/deploy/automation-wave11/edge1-contact-enrichment-research.service" /etc/systemd/system/edge1-contact-enrichment-research.service
install -m 0644 "$ROOT/deploy/automation-wave11/edge1-contact-enrichment-research.timer" /etc/systemd/system/edge1-contact-enrichment-research.timer
systemctl daemon-reload
systemctl enable --now edge1-contact-enrichment-research.timer
systemctl start edge1-contact-enrichment-research.service
systemctl start edge1-outstanding-actions.service || true
echo 'Automation wave 11 installed.'
