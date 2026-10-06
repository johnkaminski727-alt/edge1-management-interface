#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'tools/messaging/execute_wwcx_direct_mta_pilot.py'
s=p.read_text()
for marker in (
    'Audit is the default and performs no mutation',
    'WWCX_DIRECT_MTA_PILOT_AUTHORIZED',
    'ptr_forward_confirmed',
    'dkim_all_authoritative',
    'queue_state()',
    'default_transport=smtp',
    '127.0.0.1:{PILOT_PORT}',
    'smtpd_milters={MILTER}',
    'send_attempt_count',
    'rollback_succeeded',
    'raw_message_stored',
    'raw_recipient_stored',
): assert marker in s, marker
assert s.count('client.data(msg)') == 1
assert 'while True' not in s
assert 'relay_transport=smtp' not in s
assert 'smtpd_milters=inet:127.0.0.1:11332' not in s  # must remain scoped through constant/service override
assert '0.0.0.0:10026' not in s
assert '::' not in '127.0.0.1:10026'
print('WW.CX direct-MTA one-message pilot static validation passed')
print('Audit-first, exact-one-send call site, loopback-only milter service, mandatory rollback')
