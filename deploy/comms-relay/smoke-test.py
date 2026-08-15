#!/usr/bin/env python3
"""Local post-start smoke test for Edge1 Communications Relay."""
from __future__ import annotations
import argparse,json,socket,urllib.request
from pathlib import Path
def greeting(host,port,prefix):
    with socket.create_connection((host,port),timeout=3) as s:s.settimeout(3);data=s.recv(1024)
    if prefix not in data:raise SystemExit(f'unexpected greeting on {host}:{port}: {data!r}')
def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='/etc/wwcx/comms-relay.json');a=p.parse_args();cfg=json.loads(Path(a.config).read_text());listeners=cfg['listeners']
    if listeners['irc']['enabled']:greeting(listeners['irc']['host'],int(listeners['irc']['port']),b'')
    if listeners['nntp']['enabled']:greeting(listeners['nntp']['host'],int(listeners['nntp']['port']),b'200 ')
    if listeners['control']['enabled']:
        url=f"http://{listeners['control']['host']}:{listeners['control']['port']}/healthz"
        with urllib.request.urlopen(url,timeout=3) as r:payload=json.loads(r.read())
        if payload.get('status')!='ok':raise SystemExit('control health failed')
    print('PASS Edge1 Communications Relay smoke test');return 0
if __name__=='__main__':raise SystemExit(main())
