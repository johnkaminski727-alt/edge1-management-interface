#!/usr/bin/env python3
"""Export a sanitized live/source API directory for Edge1."""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

ROOT=Path('/opt/edge1-management-interface')
OUTPUT=Path('/var/www/edge1-status/api-directory/inventory.json')
PATH_RE=re.compile(r'''["']((?:/api/|/mcp|/edge1-ops/[A-Za-z0-9_./{}:-]*/api/?)[A-Za-z0-9_./{}:?=&%+\-]*)["']''')
PORT_RE=re.compile(r':(\d{2,5})\b')
API_TOKENS=('api','gateway','mail-room','contacts','telephony','mcp','portal','search','navigation-admin')
KNOWN_API_PORTS={3000,6060,8080,11332,11333,11334}

def run(*args): return subprocess.run(args,text=True,capture_output=True,check=False).stdout

def unit_for_pid(pid):
    try:
        for line in Path(f'/proc/{pid}/cgroup').read_text().splitlines():
            m=re.search(r'/([^/]+\.service)(?:$|/)',line)
            if m:return m.group(1)
    except OSError: pass
    return None

def live_listeners():
    out=run('ss','-ltnpH'); items=[]; seen=set()
    for line in out.splitlines():
        m=PORT_RE.search(line)
        pm=re.search(r'pid=(\d+)',line)
        nm=re.search(r'users:\(\("([^"\\]+)',line)
        if not m or not pm: continue
        port=int(m.group(1)); pid=int(pm.group(1)); process=nm.group(1) if nm else 'unknown'; unit=unit_for_pid(pid)
        text=f'{unit or ""} {process}'.lower()
        if not (8000 <= port <= 8999 or port in KNOWN_API_PORTS or any(t in text for t in API_TOKENS)): continue
        key=(port,unit,process)
        if key in seen: continue
        seen.add(key)
        address='loopback' if ('127.0.0.1:' in line or '[::1]:' in line) else 'network'
        desc=''
        if unit:
            show=run('systemctl','show',unit,'-p','Description','--value').strip(); desc=' '.join(show.split())[:240]
        items.append({'port':port,'bind_scope':address,'process':process,'service':unit,'description':desc,'availability':'live_verified'})
    return sorted(items,key=lambda x:(x['port'],x.get('service') or ''))

def source_endpoints():
    roots=[ROOT/'server',ROOT/'tools',ROOT/'services']
    found={}
    for base in roots:
        if not base.exists(): continue
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix not in {'.py','.js','.php','.sh'}: continue
            try:
                if path.stat().st_size>1024*1024: continue
                text=path.read_text(errors='ignore')
            except OSError: continue
            rel=str(path.relative_to(ROOT))
            for ep in PATH_RE.findall(text):
                ep=ep.split('?',1)[0]
                if len(ep)>220 or any(x in ep.lower() for x in ('token','secret','password')): continue
                key=(rel,ep)
                found[key]={'source':rel,'path':ep,'availability':'source_discovered'}
    return sorted(found.values(),key=lambda x:(x['path'],x['source']))[:2000]

def infer_boundaries(live):
    for item in live:
        text=((item.get('service') or '')+' '+item.get('description','')).lower()
        if item['bind_scope']=='loopback': exposure='loopback_only'
        else: exposure='network_listener'
        if any(x in text for x in ('readonly','read-only','search','status','telemetry')): mode='read_only'
        elif any(x in text for x in ('admin','gateway','operations','mail-room','portal')): mode='authenticated_or_bounded'
        else: mode='unknown_review_required'
        item['exposure']=exposure; item['access_boundary']=mode
    return live

def main():
    live=infer_boundaries(live_listeners()); endpoints=source_endpoints()
    data={
      'contract':'wwcx.edge1-api-directory.v1','generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
      'summary':{'live_api_listeners':len(live),'source_endpoints':len(endpoints),'loopback_listeners':sum(x['bind_scope']=='loopback' for x in live)},
      'live_apis':live,'source_endpoints':endpoints,
      'safety':{'credentials_included':False,'request_bodies_included':False,'source_discovery_does_not_imply_live_availability':True}
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(data,indent=2)+'\n'); OUTPUT.chmod(0o644)
    print(json.dumps(data['summary'],sort_keys=True))
if __name__=='__main__': main()
