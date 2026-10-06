#!/usr/bin/env python3
import json,subprocess
from pathlib import Path
PLAN=Path('/var/lib/wwcx-mail-gateway/wwcx-mx-cutover-plan.json')
p=json.loads(PLAN.read_text())
assert p['contract']=='wwcx.mx-cutover-plan.v1'
assert p['domain']=='ww.cx'
def norm(rows): return sorted((int(x['priority']),x['host'].rstrip('.').lower()+'.') for x in rows)
cut=norm(p['cutover']); rb=norm(p['rollback'])
assert cut==[(10,'mail.ww.cx.'),(50,'mx1.privateemail.com.'),(60,'mx2.privateemail.com.')]
assert rb==[(10,'mx1.privateemail.com.'),(20,'mx2.privateemail.com.')]
assert len({x for _,x in cut})==3
for ns in p['authoritative_nameservers']:
    out=subprocess.check_output(['dig','+short','@'+ns,'ww.cx','MX'],text=True,timeout=8)
    live=sorted((int(line.split()[0]),line.split()[1].rstrip('.').lower()+'.') for line in out.splitlines() if line.strip())
    assert live==rb,(ns,live,rb)
print('WW.CX MX cutover plan validation passed')
print('Current authoritative MX equals rollback baseline on all four Dyn nameservers')
print('No production MX mutation performed')
