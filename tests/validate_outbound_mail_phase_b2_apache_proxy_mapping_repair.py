#!/usr/bin/env python3
"""Validate the bounded Phase B2 Apache proxy-mapping repair package."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-mapping.sh"
TEMPLATE = ROOT / "deploy/messaging/outbound-mail-preparation-api-apache.conf.example"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-b2-apache-proxy-mapping-repair-20260804.md"

for path in (SCRIPT, TEMPLATE, RUNBOOK):
    assert path.is_file(), path

script = SCRIPT.read_text(encoding="utf-8")
for required in (
    "set -eu",
    "umask 077",
    "ACTION=${ACTION:-audit}",
    "APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED=${APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED:-no}",
    "ROLLBACK_EVIDENCE=${ROLLBACK_EVIDENCE:-}",
    "GIT_OPTIONAL_LOCKS=0 git -C \"$REPO_ROOT\" status --porcelain --untracked-files=all",
    "FRAGMENT_PATH=/etc/apache2/wwcx-outbound-mail-preparation-api.conf",
    "VHOST_TARGET=/etc/apache2/sites-available/edge1.ww.cx.conf",
    "Require ip 162.0.217.71/32",
    "expected exactly two legacy ProxyPass mappings",
    "candidate changes more than the two proxy directive names",
    "ProxyPassMatch",
    "apache2ctl configtest",
    'systemctl reload "$APACHE_SERVICE"',
    "trap on_exit EXIT HUP INT TERM",
    "automatic_rollback=pass",
    "live fragment drifted after repair",
    "ready_for_explicit_apache_proxy_mapping_repair_authorization",
    "awaiting_business159_source_acceptance",
    "hmac_secret_read no",
    "provider_or_sender_enabled no",
    "external_delivery_enabled no",
    "message_prepared no",
    "message_sent no",
    "SHA256SUMS",
):
    assert required in script, required

for forbidden in (
    "systemctl restart",
    "systemctl stop",
    "systemctl start",
    "systemctl enable",
    "systemctl disable",
    "a2enmod",
    "a2ensite",
    "certbot",
    "openssl pkey",
    "openssl rsa",
    "WWCX_MAIL_GATEWAY_TOKEN=",
    "nft add",
    "iptables -A",
    "ufw allow",
    "nsupdate",
    "/outbound-mail/send\" retry=",
):
    assert forbidden not in script, forbidden

assert script.index("trap on_exit EXIT HUP INT TERM") < script.index(
    'install -o root -g root -m 0644 "$EVIDENCE_DIR/fragment.candidate.conf" "$FRAGMENT_PATH"'
)
assert script.index('apache2ctl configtest > "$EVIDENCE_DIR/configtest.txt"') < script.index(
    'systemctl reload "$APACHE_SERVICE" > "$EVIDENCE_DIR/apache-reload.txt"'
)
assert script.index("live fragment drifted after repair") < script.index(
    'cp -a -- "$ROLLBACK_EVIDENCE/fragment.before.conf" "$FRAGMENT_PATH"'
)
assert script.count("record message_sent no") == 2
assert script.count("record external_delivery_enabled no") == 2

syntax = subprocess.run(["sh", "-n", str(SCRIPT)], cwd=ROOT, check=False)
assert syntax.returncode == 0

template = TEMPLATE.read_text(encoding="utf-8")
assert template.count('ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/') == 2
assert template.count('\n    ProxyPass "') == 0
assert template.count("Require ip PREPARATION_CLIENT_CIDR") == 2
assert "/outbound-mail/send" not in template

legacy = template.replace("ProxyPassMatch", "ProxyPass")
assert legacy.count('ProxyPass "http://127.0.0.1:8104/outbound-mail/api/v1/') == 2
candidate = legacy.replace(
    '    ProxyPass "http://127.0.0.1:8104/outbound-mail/api/v1/',
    '    ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/',
)
assert candidate == template

runbook = RUNBOOK.read_text(encoding="utf-8")
for required in (
    "Business159",
    "162.0.217.71",
    "HTTP `404`",
    "HTTP `401`",
    "ProxyPassMatch",
    "ACTION=audit",
    "APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED=yes",
    "automatic rollback",
    "Do not install the Business159 credential",
    "no message",
):
    assert required in runbook, required

print("Outbound mail Apache proxy-mapping repair validation passed")
print("Exactly two ProxyPass directives are converted to ProxyPassMatch")
print("Audit defaults, exact-commit checks, Git ownership protection, and automatic rollback are enforced")
print("Credentials, provider activation, delivery, and message traffic remain blocked")
