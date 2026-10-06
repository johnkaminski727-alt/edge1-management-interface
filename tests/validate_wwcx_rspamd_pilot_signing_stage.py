#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script = ROOT / "deploy/messaging/apply-wwcx-rspamd-pilot-signing-stage.sh"
text = script.read_text()

required = (
    'selector = "edge1-202610";',
    'path = "/var/lib/rspamd/dkim/$domain.$selector.key";',
    'sign_networks = ["127.0.0.0/8"];',
    'bind_socket = "127.0.0.1:11332";',
    'hosts = "127.0.0.1:11333";',
    'rspamadm configtest',
    'systemctl restart rspamd',
    'postconf -h smtpd_milters',
    'postconf -h non_smtpd_milters',
    'postconf -h default_transport',
    'postconf -h relay_transport',
)
for marker in required:
    assert marker in text, marker

for forbidden in (
    'postconf -e',
    'sendmail',
    '/usr/sbin/sendmail',
    'nsupdate',
    'dig ',
    'ufw allow',
    'default_transport=smtp',
    'relay_transport=smtp',
    'smtpd_milters=',
    'non_smtpd_milters=',
):
    assert forbidden not in text, forbidden

assert '127.0.0.1:11332' in text
assert '0.0.0.0:11332' not in text
assert '[::]:11332' not in text
print('WW.CX Rspamd pilot signing stage validation passed')
print('Signing proxy is loopback-only and installer cannot enable Postfix outbound or milter hooks')
