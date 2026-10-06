#!/usr/bin/env python3
"""Publish a key-free WireGuard peer inventory for downstream identity telemetry."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from typing import Any

DEFAULT_WG=Path('/etc/wireguard/wg0.conf')
DEFAULT_OUTPUT=Path('/var/cache/edge1-wireguard-telemetry/wireguard-peers.json')

def parse(text:str)->list[dict[str,Any]]:
    peers=[]; current=None; pending=''
    for raw in text.splitlines():
        line=raw.strip()
        if not line: continue
        if line.startswith('#'):
            label=line[1:].strip()[:160]
            if current is not None and not current.get('name'): current['name']=label
            else: pending=label
            continue
        if line.lower()=='[peer]':
            if current is not None: peers.append(current)
            current={'name':pending,'assigned_addresses':[]}; pending=''; continue
        if current is None or '=' not in line: continue
        key,value=(part.strip() for part in line.split('=',1))
        if key.lower()=='allowedips':
            current['assigned_addresses']=[x.strip() for x in value.split(',') if x.strip()]
    if current is not None: peers.append(current)
    return peers

def write_atomic(path:Path,payload:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.tmp')
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    os.chmod(tmp,0o644); tmp.replace(path)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--wg-config',type=Path,default=DEFAULT_WG); ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); a=ap.parse_args()
    peers=parse(a.wg_config.read_text(encoding='utf-8'))
    payload={'schema_version':1,'contract':'wwcx.wireguard-peer-inventory.v1','contains_keys':False,'peers':peers}
    write_atomic(a.output,payload)
    print(json.dumps({'ok':True,'peer_count':len(peers),'output':str(a.output)},sort_keys=True))
if __name__=='__main__':main()
