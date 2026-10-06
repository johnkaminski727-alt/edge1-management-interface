#!/usr/bin/env python3
"""Privacy-limited per-device DNS/security telemetry for managed WireGuard peers."""
from __future__ import annotations
import argparse, json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

DEFAULT_IDENTITY=Path('/var/www/edge1-status/wireguard-identity.json')
DEFAULT_QUERYLOG=Path('/opt/AdGuardHome/data/querylog.json')
DEFAULT_CROWDSEC=Path('/var/www/edge1-status/crowdsec-status.json')
DEFAULT_OUTPUT=Path('/var/www/edge1-status/wireguard-dns-security.json')
DEFAULT_IDENTITY_PUBLISH=Path('/var/www/edge1-status/wireguard-identity.json')

def parse_time(value:str):
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None

def build(identity_path:Path, querylog_path:Path, crowdsec_path:Path, hours:int=24)->dict[str,Any]:
    identity=json.loads(identity_path.read_text())
    devices=identity.get('devices') or []
    by_ip={}
    for d in devices:
        for a in d.get('assigned_addresses') or []: by_ip[a.split('/',1)[0]]=d
    now=datetime.now(timezone.utc); cutoff=now-timedelta(hours=max(1,hours))
    stats={ip:{'queries':0,'blocked':0,'last_query_at':None,'filter_lists':Counter()} for ip in by_ip}
    if querylog_path.exists():
        with querylog_path.open(encoding='utf-8',errors='ignore') as fh:
            for line in fh:
                try:q=json.loads(line)
                except Exception:continue
                ip=q.get('IP'); t=parse_time(str(q.get('T') or ''))
                if ip not in stats or t is None or t<cutoff: continue
                s=stats[ip]; s['queries']+=1
                if s['last_query_at'] is None or t.isoformat()>s['last_query_at']: s['last_query_at']=t.isoformat()
                result=q.get('Result') if isinstance(q.get('Result'),dict) else {}
                if result.get('IsFiltered') is True:
                    s['blocked']+=1
                    for rule in result.get('Rules') or []:
                        if isinstance(rule,dict) and rule.get('FilterListID') is not None: s['filter_lists'][str(rule['FilterListID'])]+=1
    crowd={}
    if crowdsec_path.exists():
        try:crowd=json.loads(crowdsec_path.read_text())
        except Exception:crowd={}
    services=crowd.get('services') if isinstance(crowd.get('services'),dict) else {}
    crowd_ok=bool((services.get('crowdsec') or {}).get('active')) and bool((services.get('crowdsec-firewall-bouncer') or {}).get('active'))
    rows=[]
    for ip,d in by_ip.items():
        s=stats[ip]
        rows.append({
            'name':d.get('name'),'owner_subject':d.get('owner_subject'),'address':ip,
            'dns':{'queries_24h':s['queries'],'blocked_24h':s['blocked'],'block_rate':round(s['blocked']/s['queries'],4) if s['queries'] else 0.0,'last_query_at':s['last_query_at'],'filter_list_hits':dict(s['filter_lists'])},
            'security':{'crowdsec_observed':crowd_ok,'spamhaus_enabled':bool((d.get('security') or {}).get('spamhaus_enabled')),'quarantined':bool((d.get('security') or {}).get('quarantined'))}
        })
    return {'schema_version':1,'contract':'wwcx.wireguard-dns-security.v1','generated_at':now.isoformat(),'window_hours':hours,'privacy':{'domain_names_exported':False,'raw_keys_exported':False},'crowdsec':{'active':crowd_ok,'generated_at':crowd.get('generated_at')},'devices':rows,'summary':{'device_count':len(rows),'queries_24h':sum(r['dns']['queries_24h'] for r in rows),'blocked_24h':sum(r['dns']['blocked_24h'] for r in rows),'crowdsec_active':crowd_ok}}

def write_atomic(path:Path,payload:dict):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name('.'+path.name+'.tmp'); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); tmp.replace(path)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--identity',type=Path,default=DEFAULT_IDENTITY); ap.add_argument('--querylog',type=Path,default=DEFAULT_QUERYLOG); ap.add_argument('--crowdsec',type=Path,default=DEFAULT_CROWDSEC); ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); ap.add_argument('--identity-publish',type=Path,default=DEFAULT_IDENTITY_PUBLISH); ap.add_argument('--hours',type=int,default=24); a=ap.parse_args(); identity_payload=json.loads(a.identity.read_text()); write_atomic(a.identity_publish, identity_payload); p=build(a.identity,a.querylog,a.crowdsec,a.hours); write_atomic(a.output,p); print(json.dumps({'ok':True,'output':str(a.output),**p['summary']},sort_keys=True))
if __name__=='__main__':main()
