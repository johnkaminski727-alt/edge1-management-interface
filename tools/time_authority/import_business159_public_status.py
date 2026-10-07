#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, tempfile, urllib.request
from pathlib import Path

DEFAULT_URL='https://ww.cx/api/time-status.php'
DEFAULT_OUTPUT=Path('/var/lib/edge1-time-authority/business159-measurements.jsonl')

def fetch(url:str)->dict:
    req=urllib.request.Request(url,headers={'User-Agent':'WWCX-Edge1-TimeAuthority/1'})
    with urllib.request.urlopen(req,timeout=10) as r:
        if r.status != 200: raise RuntimeError(f'HTTP {r.status}')
        data=json.load(r)
    if not isinstance(data,dict) or data.get('schema_version') != 1:
        raise RuntimeError('unexpected status schema')
    return data

def latest_timestamp(path:Path)->str|None:
    if not path.is_file(): return None
    last=None
    with path.open('r',encoding='utf-8',errors='replace') as h:
        for line in h:
            try:
                value=json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value,dict) and value.get('observed_at_utc'):
                last=str(value['observed_at_utc'])
    return last

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--url',default=DEFAULT_URL)
    p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    a=p.parse_args()
    data=fetch(a.url)
    ntp=data.get('ntp') if isinstance(data.get('ntp'),dict) else {}
    observed=ntp.get('observed_at_utc')
    if not isinstance(observed,str) or not observed:
        raise RuntimeError('missing observed_at_utc')
    if latest_timestamp(a.output) == observed:
        print(json.dumps({'ok':True,'changed':False,'observed_at_utc':observed}))
        return 0
    service=data.get('service') if isinstance(data.get('service'),dict) else {}
    record={
        'schema_version':1,
        'observed_at_utc':observed,
        'observer_id':'business159',
        'observer_host':'business159.web-hosting.com',
        'source_id':'wwcx-public-ntp',
        'server_name':str(service.get('canonical_host') or 'ntp.ww.cx'),
        'resolved_address':ntp.get('resolved_address'),
        'provider':'WW.CX',
        'region':'Edge1 public service',
        'stratum':ntp.get('stratum'),
        'refid':None,
        'rtt_ms':ntp.get('rtt_ms'),
        'network_delay_ms':None,
        'clock_offset_ms':ntp.get('clock_offset_ms'),
        'root_delay_ms':None,
        'root_dispersion_ms':None,
        'reachable':bool(ntp.get('reachable')),
        'expectation_ok':bool(ntp.get('reachable')) and not bool((data.get('observer') or {}).get('stale')),
        'error':None if ntp.get('reachable') else 'public observer reports NTP unreachable',
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o640)
    try:
        os.write(fd,(json.dumps(record,separators=(',',':'))+'\n').encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps({'ok':True,'changed':True,'observed_at_utc':observed,'reachable':record['reachable']}))
    return 0
if __name__=='__main__': raise SystemExit(main())
