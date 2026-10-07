#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from datetime import datetime, timezone
from pathlib import Path

def fail(msg): raise SystemExit(f'HIDDEN_PRIMARY_PREPARE=FAIL: {msg}')

def live_serial(zone: str, ns: str) -> int:
    p=subprocess.run(['/usr/bin/dig','+short','+time=5','+tries=1','@'+ns,zone,'SOA'],text=True,capture_output=True)
    if p.returncode or not p.stdout.strip(): fail(f'cannot read live SOA from {ns}')
    parts=p.stdout.split()
    if len(parts)<3 or not parts[2].isdigit(): fail(f'unexpected SOA response from {ns}')
    return int(parts[2])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--inventory',type=Path,required=True)
    ap.add_argument('--zone-file',type=Path,required=True)
    ap.add_argument('--authoritative-ns',default='ns1194.dns.dyn.com')
    a=ap.parse_args()
    inv=json.loads(a.inventory.read_text())
    if inv.get('complete_zone_inventory') is not True: fail('inventory is not complete')
    text=a.zone_file.read_text()
    m=re.search(r'(\bSOA\b[^\n]*\(\s*\n?\s*)(\d+)(\s*;\s*serial number)',text,re.I)
    if not m: fail('cannot locate Dyn export SOA serial')
    exported=int(m.group(2)); live=live_serial(inv.get('zone','ww.cx.'),a.authoritative_ns)
    new=(live+1) & 0xffffffff
    if new == 0: new=1
    # RFC 1982: ensure chosen serial is newer than live for this normal non-wrap case.
    if ((new-live) & 0xffffffff) == 0 or ((new-live) & 0xffffffff) >= 0x80000000:
        fail('could not derive a newer RFC1982 serial')
    updated=text[:m.start(2)] + str(new) + text[m.end(2):]
    a.zone_file.write_text(updated)
    digest=hashlib.sha256(a.zone_file.read_bytes()).hexdigest()
    inv['zone_file_sha256']=digest
    inv['exported_soa_serial']=exported
    inv['observed_public_soa_serial']=live
    inv['candidate_soa_serial']=new
    inv['candidate_prepared_at_utc']=datetime.now(timezone.utc).isoformat(timespec='seconds')
    inv['notes']='Imported from Dyn Standard DNS export; candidate serial advanced beyond current public Dyn SOA. Activation remains separately gated.'
    a.inventory.write_text(json.dumps(inv,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'ok':True,'exported_serial':exported,'public_serial':live,'candidate_serial':new,'sha256':digest},sort_keys=True))
if __name__=='__main__': main()
