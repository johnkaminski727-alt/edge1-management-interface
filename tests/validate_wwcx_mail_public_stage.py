from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
script=(root/'deploy/messaging/apply-wwcx-mail-public-stage.sh').read_text()
cfg=json.loads((root/'config/messaging/wwcx-mail-canary.json').read_text())
assert 'inet_interfaces=127.0.0.1, $MAIL_IP' in script
assert 'smtpd_tls_cert_file=$CERT' in script
assert 'smtpd_tls_key_file=$KEY' in script
assert 'Outbound delivery disabled during commissioning' in script
assert 'Outbound relay disabled during commissioning' in script
assert 'reject_unauth_destination' in script
assert 'ufw allow 25/tcp' in script
assert cfg['activation']['public_smtp_listener_enabled'] is True
assert cfg['activation']['production_mx_changed'] is False
assert cfg['activation']['outbound_delivery_enabled'] is False
assert cfg['activation']['other_domains_migration_enabled'] is False
print('PASS')
