#!/usr/bin/env python3
"""Static safety validation for the Phase B2 Apache activation package."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/messaging/activate-outbound-mail-phase-b2-apache.sh"
TEMPLATE = ROOT / "deploy/messaging/outbound-mail-preparation-api-apache.conf.example"
ACCEPTANCE = ROOT / "docs/messaging-operations/outbound-mail-phase-b2-apache-proposal-live-acceptance-20260801.md"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-b2-apache-activation-20260801.md"
STATE = ROOT / ".agent/outbound-mail-b2-readiness.md"

for path in (SCRIPT, TEMPLATE, ACCEPTANCE, RUNBOOK, STATE):
    assert path.is_file(), path

text = SCRIPT.read_text(encoding="utf-8")
for value in (
    "set -eu",
    "umask 077",
    "EXPECTED_COMMIT=${EXPECTED_COMMIT:-}",
    "APPROVED_ACTIVATION_COMMIT=${APPROVED_ACTIVATION_COMMIT:-}",
    "PROPOSAL_PACKAGE_COMMIT=${PROPOSAL_PACKAGE_COMMIT:-105ea0f2dd79a3bbc5a09c5c7c7ed49eab5a0e0d}",
    "PROPOSAL_EVIDENCE=${PROPOSAL_EVIDENCE:-/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal/20260801T210934Z}",
    "ACTION=${ACTION:-install}",
    "ROLLBACK_EVIDENCE=${ROLLBACK_EVIDENCE:-}",
    "PROPOSED_CLIENT_CIDR=162.0.217.71/32",
    "ACTIVE_VHOST=/etc/apache2/sites-enabled/edge1.ww.cx.conf",
    "FRAGMENT_PATH=/etc/apache2/wwcx-outbound-mail-preparation-api.conf",
    "git -C \"$REPO_ROOT\" status --porcelain --untracked-files=all",
    "git -C \"$REPO_ROOT\" merge-base --is-ancestor",
    "protected Phase B2 files changed after the approved activation baseline",
    "sha256sum -c SHA256SUMS",
    "readiness_state=ready_for_explicit_b2_apache_authorization",
    "proposal evidence contains failures",
    "127.0.0.1:8104",
    "direct unsigned preparation status is not HTTP 401",
    "direct send endpoint is not HTTP 403",
    "render_candidate",
    "patch_vhost",
    "expected exactly one approved TLS vhost",
    "vhost patch changed more than the one approved include line",
    "vhost.before.conf",
    "fragment.before.state",
    "candidate-apache-fragment.conf",
    "apache2ctl configtest",
    "systemctl reload \"$APACHE_SERVICE\"",
    "unapproved local source was not denied on the status route",
    "unapproved local source was not denied on the prepare route",
    "HTTPS send route is unexpectedly exposed",
    "HTTPS health route is unexpectedly exposed",
    "automatic_rollback=pass",
    "live vhost changed after activation; refusing to overwrite it",
    "live fragment changed after activation; refusing to overwrite it",
    "approved_source_external_canary not_yet_run",
    "readiness_state awaiting_business159_source_acceptance",
    "certificate_private_key_exposed no",
    "certificate_key_pair_validated_by_apache yes",
    "hmac_secret_read no",
    "external_delivery_enabled no",
    "message_sent no",
    "SHA256SUMS",
):
    assert value in text, value

for forbidden in (
    "systemctl restart",
    "systemctl stop",
    "systemctl start",
    "systemctl enable",
    "systemctl disable",
    "a2enconf",
    "a2ensite",
    "a2enmod",
    "certbot",
    "acme.sh",
    "openssl pkey",
    "openssl rsa",
    "openssl ec",
    "openssl pkcs8",
    'cat "$CERTIFICATE_PRIVATE_KEY_PATH"',
    'sha256sum "$CERTIFICATE_PRIVATE_KEY_PATH"',
    "WWCX_MAIL_GATEWAY_TOKEN=",
    "nft add",
    "nft delete",
    "iptables -A",
    "iptables -I",
    "iptables -D",
    "ufw allow",
    "ufw deny",
    "firewall-cmd",
    "nsupdate",
):
    assert forbidden not in text, forbidden

assert text.count('record message_sent no') == 2
assert text.count('record external_delivery_enabled no') == 2
assert text.index("trap on_exit EXIT") < text.index('install -o root -g root -m 0644 "$EVIDENCE_DIR/candidate-apache-fragment.conf"')
assert text.index("apache2ctl configtest > \"$EVIDENCE_DIR/configtest.txt\"") < text.index('systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/apache-reload.txt"')
assert text.index("live vhost changed after activation") < text.index('cp -a -- "$ROLLBACK_EVIDENCE/vhost.before.conf" "$VHOST_TARGET"')

syntax = subprocess.run(["sh", "-n", str(SCRIPT)], cwd=ROOT, check=False)
assert syntax.returncode == 0

template = TEMPLATE.read_text(encoding="utf-8")
assert template.count("Require ip PREPARATION_CLIENT_CIDR") == 2
assert template.count('<LocationMatch "^/outbound-mail/api/v1/status$">') == 1
assert template.count('<LocationMatch "^/outbound-mail/api/v1/prepare$">') == 1
assert template.count('ProxyPassMatch "http://127.0.0.1:8104"') == 2
assert 'ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/status"' not in template
assert 'ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/prepare"' not in template
assert "Apache appends" in template
assert "duplicate the path" in template
assert '\n    ProxyPass "' not in template
assert "/outbound-mail/send" not in template

acceptance = ACCEPTANCE.read_text(encoding="utf-8")
for value in (
    "2026-08-01T21:09:34Z",
    "20260801T210934Z",
    "d89cbb06d5ecd171e67c1a281beb58ef16a1f24c",
    "105ea0f2dd79a3bbc5a09c5c7c7ed49eab5a0e0d",
    "edge1_servername_count=2",
    "fullchain_reference_count=1",
    "private_key_reference_count=1",
    "fullchain2.pem",
    "privkey2.pem",
    "readiness_state=ready_for_explicit_b2_apache_authorization",
    "failures=0",
    "No Apache file was installed",
):
    assert value in acceptance, value

runbook = RUNBOOK.read_text(encoding="utf-8")
for value in (
    "/etc/apache2/wwcx-outbound-mail-preparation-api.conf",
    "IncludeOptional /etc/apache2/wwcx-outbound-mail-preparation-api.conf",
    "automatic rollback",
    "awaiting_business159_source_acceptance",
    "ACTION=rollback",
    "refuses rollback if the live vhost or fragment has changed",
    "Production message: not defined or sent",
):
    assert value in runbook, value

state = STATE.read_text(encoding="utf-8")
for value in (
    "2026-08-01T21:09:34Z",
    "20260801T210934Z",
    "ready_for_explicit_b2_apache_authorization",
    "Apache activation package: **in repository review**",
    "public preparation route: **not yet activated**",
    "production message: **not defined or sent**",
):
    assert value in state, value

print("Outbound mail Phase B2 Apache activation validation passed")
print("Exact-route activation, drift-safe rollback, and no-send boundaries are enforced")
print("LocationMatch proxy mappings use origin-only ProxyPassMatch targets")
print("Business159 source acceptance remains a separate post-activation gate")
