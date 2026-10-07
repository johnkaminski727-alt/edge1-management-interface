#!/usr/bin/env python3
"""Reclassify only completed checks affected by the approved catch-all policy."""
import collections
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from server.mail_room_security import SecurityStore


def main():
    security=SecurityStore();identities=json.loads(Path('/etc/wwcx/outbound-mail/identities.json').read_text());policy=json.loads(Path('/etc/wwcx/mail-security-policy.json').read_text())
    catchalls=set(identities.get('catch_all_domains',{}));external=set(policy.get('authenticated_external_identities',[]))
    with sqlite3.connect('file:/var/lib/wwcx-mail-room/correspondence.sqlite3?mode=ro',uri=True) as db:
        indexed={hashlib.sha256(mid.encode()).hexdigest():(mid,sender) for mid,sender in db.execute('select message_id,sender from correspondence')}
    recipients={}
    for path in Path('/var/lib/wwcx-mail-gateway/inbound').glob('*/*/metadata.json'):
        item=json.loads(path.read_text());key=item.get('normalization',{}).get('message_id_sha256')
        if key:recipients.setdefault(key,set()).add(item['envelope_recipient'].rsplit('@',1)[-1].lower())
    with security.connect() as db:rows=db.execute("select message_hash,raw_hash,payload from decisions where state='quarantine'").fetchall()
    counts=collections.Counter()
    for key,raw_hash,payload in rows:
        decision=json.loads(payload);reasons=set(decision.get('reasons',[]));remove=set()
        if key not in indexed or not decision.get('scan_complete') or decision.get('hard_block'):continue
        if recipients.get(key) and recipients[key]<=catchalls:remove.add('unregistered_catch_all_recipient_review')
        auth=decision.get('authentication',{})
        if indexed[key][1] in external and auth.get('dkim')=='pass' and auth.get('dmarc')=='pass':remove.add('protected_display_name_impersonation')
        remove&=reasons
        if not remove or reasons-remove-{'checks_passed','reply_to_domain_differs'}:continue
        decision['reasons']=[r for r in decision['reasons'] if r not in remove];decision['state']='released'
        security.write(indexed[key][0],raw_hash,decision);counts[security.get(indexed[key][0])['state']]+=1
    print(json.dumps({'reclassified':dict(counts),'malware_or_incomplete_checks_bypassed':False}))

if __name__=='__main__':main()
