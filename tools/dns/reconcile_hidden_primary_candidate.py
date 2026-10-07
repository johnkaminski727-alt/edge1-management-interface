#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess
from pathlib import Path

def norm_rdata(s):
    s=' '.join(s.split())
    # Dyn/dig may split long TXT strings into adjacent quoted chunks; compare their joined content.
    chunks=re.findall(r'"((?:\\.|[^"])*)"',s)
    if chunks and s.lstrip().startswith('"'):
        return 'TXT:' + ''.join(chunks).replace('\\;',';')
    return s.rstrip('.').lower()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--zone-file',type=Path,required=True); ap.add_argument('--zone',default='ww.cx'); ap.add_argument('--nameserver',action='append',required=True); a=ap.parse_args()
    c=subprocess.run(['/usr/bin/named-checkzone','-D','-o','-',a.zone,str(a.zone_file)],text=True,capture_output=True,check=True).stdout
    expected={}
    for line in c.splitlines():
        m=re.match(r'^(\S+)\s+\d+\s+IN\s+(\S+)\s+(.+)$',line)
        if not m: continue
        name,typ,rdata=m.groups()
        if typ.upper()=='SOA': continue
        expected.setdefault((name.rstrip('.'),typ.upper()),set()).add(norm_rdata(rdata))
    failures=[]; checked=0
    for ns in a.nameserver:
        for (name,typ),want in sorted(expected.items()):
            p=subprocess.run(['/usr/bin/dig','+short','+time=5','+tries=1','@'+ns,name,typ],text=True,capture_output=True)
            got={norm_rdata(x) for x in p.stdout.splitlines() if x.strip()}
            checked += 1
            if got != want:
                failures.append({'nameserver':ns,'name':name,'type':typ,'expected':sorted(want),'observed':sorted(got)})
    out={'ok':not failures,'zone':a.zone+'.','nameservers':a.nameserver,'rrsets_checked':checked,'mismatch_count':len(failures),'mismatches':failures}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if not failures else 1)
if __name__=='__main__': main()
