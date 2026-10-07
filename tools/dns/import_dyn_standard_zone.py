#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, shutil
from datetime import datetime, timezone
from pathlib import Path

ZONE = 'ww.cx.'
CONTRACT = 'wwcx.authoritative-zone-inventory.v1'

def fail(msg: str) -> None:
    raise SystemExit(f'DYN_ZONE_IMPORT=FAIL: {msg}')

def logical_records(text: str) -> list[str]:
    out=[]; buf=[]; depth=0
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith(';'): continue
        if line.upper().startswith('$INCLUDE'): fail('$INCLUDE is not permitted in imported authoritative zone files')
        # Strip comments only when outside quotes.
        q=False; esc=False; clean=[]
        for ch in raw:
            if esc: clean.append(ch); esc=False; continue
            if ch=='\\': clean.append(ch); esc=True; continue
            if ch=='"': q=not q; clean.append(ch); continue
            if ch==';' and not q: break
            clean.append(ch)
        s=''.join(clean).strip()
        if not s: continue
        if s.startswith('$'):
            out.append(s)
            continue
        depth += s.count('(') - s.count(')')
        buf.append(s)
        if depth <= 0:
            out.append(' '.join(buf)); buf=[]; depth=0
    if buf: fail('unterminated parenthesized record')
    return out

def main() -> None:
    ap=argparse.ArgumentParser(description='Import a complete Dyn Standard DNS zone export into the guarded Edge1 hidden-primary candidate workspace.')
    ap.add_argument('export_file', type=Path)
    ap.add_argument('--state-dir', type=Path, default=Path('/var/lib/edge1-authoritative-dns'))
    ap.add_argument('--confirm-complete-dyn-export', action='store_true')
    a=ap.parse_args()
    if not a.confirm_complete_dyn_export:
        fail('explicit --confirm-complete-dyn-export is required')
    if not a.export_file.is_file(): fail('export file does not exist')
    raw=a.export_file.read_bytes()
    try: text=raw.decode('utf-8-sig','strict')
    except UnicodeDecodeError as exc: fail(f'zone export must be UTF-8 text: {exc}')
    records=logical_records(text)
    directives=[r for r in records if r.startswith('$')]
    data=[r for r in records if not r.startswith('$')]
    origin=[r for r in directives if r.upper().startswith('$ORIGIN')]
    if origin:
        parts=origin[-1].split()
        if len(parts)<2 or parts[1].lower().rstrip('.')+'.' != ZONE:
            fail(f'zone origin must be {ZONE}')
    if not any(re.search(r'\bSOA\b', r, re.I) for r in data): fail('SOA record missing')
    if not any(re.search(r'\bNS\b', r, re.I) for r in data): fail('NS record missing')
    if len(data) < 3: fail('export contains too few resource records to be accepted as complete')
    state=a.state_dir
    state.mkdir(parents=True, exist_ok=True)
    original=state/'ww.cx.dyn-export.txt'
    candidate=state/'ww.cx.zone'
    inventory=state/'ww.cx-inventory.json'
    shutil.copyfile(a.export_file, original)
    candidate.write_text(text if text.endswith('\n') else text+'\n')
    digest=hashlib.sha256(candidate.read_bytes()).hexdigest()
    payload={
      'schema_version':1,
      'contract':CONTRACT,
      'zone':ZONE,
      'complete_zone_inventory':True,
      'source':'Dyn Standard DNS Export Zone',
      'exported_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
      'record_count':len(data),
      'zone_file_sha256':digest,
      'original_export_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
      'original_export_file':str(original),
      'candidate_zone_file':str(candidate),
      'notes':'Imported from the Dyn Standard DNS Export Zone function; activation remains separately gated.'
    }
    inventory.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    for p in (original,candidate,inventory): p.chmod(0o640)
    print(json.dumps({'ok':True,'zone':ZONE,'record_count':len(data),'candidate':str(candidate),'inventory':str(inventory),'sha256':digest,'activation':'still_gated'},sort_keys=True))
if __name__=='__main__': main()
