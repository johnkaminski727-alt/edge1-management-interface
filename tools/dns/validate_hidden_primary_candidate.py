#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

def fail(msg: str) -> None:
    raise SystemExit(f"HIDDEN_PRIMARY_CANDIDATE=FAIL: {msg}")

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--inventory', type=Path, required=True)
    ap.add_argument('--zone-file', type=Path, required=True)
    a=ap.parse_args()
    if not a.inventory.is_file(): fail('complete zone inventory manifest is missing')
    if not a.zone_file.is_file(): fail('candidate zone file is missing')
    try: inv=json.loads(a.inventory.read_text())
    except Exception as exc: fail(f'inventory JSON invalid: {exc}')
    if inv.get('contract') != 'wwcx.authoritative-zone-inventory.v1': fail('inventory contract mismatch')
    if inv.get('zone') != 'ww.cx.': fail('inventory zone must be ww.cx.')
    if inv.get('complete_zone_inventory') is not True: fail('inventory is not explicitly marked complete')
    raw=a.zone_file.read_bytes(); text=raw.decode('utf-8','strict')
    digest=hashlib.sha256(raw).hexdigest()
    if inv.get('zone_file_sha256') != digest: fail('zone file SHA-256 does not match inventory manifest')
    count=int(inv.get('record_count') or 0)
    if count < 1: fail('record_count must be positive')
    meaningful=[]
    for line in text.splitlines():
        line=line.split(';',1)[0].strip()
        if line and not line.startswith('$'): meaningful.append(line)
    if not any(re.search(r'\bSOA\b',x,re.I) for x in meaningful): fail('SOA record missing')
    if not any(re.search(r'\bNS\b',x,re.I) for x in meaningful): fail('NS record missing')
    if len(meaningful) < count: fail('zone content contains fewer records than inventory record_count')
    print(json.dumps({'ok':True,'zone':'ww.cx.','record_count':count,'sha256':digest,'activation_gate':'candidate_validated'},sort_keys=True))
if __name__=='__main__': main()
