#!/usr/bin/env python3
import json
from pathlib import Path
cfg=json.loads(Path('config/messaging/wwcx-mail-canary.json').read_text())
g=cfg['cutover_gates']
assert g['outbound_preflight_ready'] is True
assert g['rollback_transaction_validated'] is True
assert g['outbound_one_message_pilot'] is False
assert g['rollback_rehearsal'] is False
assert cfg['activation']['production_mx_changed'] is False
assert cfg['activation']['outbound_delivery_enabled'] is False
print('WW.CX final preconditions validation passed')
