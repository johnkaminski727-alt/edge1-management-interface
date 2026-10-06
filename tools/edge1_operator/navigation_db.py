#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from server.edge1_navigation_registry import connect, migrate, import_registry, export_registry, atomic_write_json, set_enabled, set_theme

DEFAULT_DB=Path('/var/lib/edge1-navigation/navigation.sqlite3')
DEFAULT_BOOTSTRAP=ROOT/'config/edge1_operator/navigation_registry.json'
DEFAULT_OUTPUT=Path('/var/www/edge1-status/operator-shell/navigation.json')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--database',type=Path,default=DEFAULT_DB)
    sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('init'); q.add_argument('--bootstrap',type=Path,default=DEFAULT_BOOTSTRAP); q.add_argument('--replace',action='store_true')
    q=sub.add_parser('export'); q.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); q.add_argument('--include-disabled',action='store_true')
    q=sub.add_parser('list'); q.add_argument('--all',action='store_true')
    q=sub.add_parser('enable'); q.add_argument('module_id')
    q=sub.add_parser('disable'); q.add_argument('module_id')
    q=sub.add_parser('theme'); q.add_argument('module_id'); q.add_argument('theme',choices=['inherit','light','dark'])
    a=p.parse_args()
    ro=a.cmd in {'export','list'}
    if a.cmd=='init':
        with connect(a.database) as c: import_registry(c,json.loads(a.bootstrap.read_text()),replace=a.replace)
        print(f'initialized={a.database}')
    elif a.cmd=='export':
        with connect(a.database,read_only=True) as c: payload=export_registry(c,include_disabled=a.include_disabled)
        atomic_write_json(a.output,payload)
        print(json.dumps({'ok':True,'modules':len(payload['modules']),'output':str(a.output)}))
    elif a.cmd=='list':
        with connect(a.database,read_only=True) as c: payload=export_registry(c,include_disabled=a.all)
        for m in payload['modules']:
            print(f"{m['id']}\t{int(m['enabled'])}\t{m['theme']}\t{m['section']}\t{m['label']}\t{m.get('browser_route') or '-'}")
    elif a.cmd in {'enable','disable'}:
        with connect(a.database) as c: set_enabled(c,a.module_id,a.cmd=='enable')
        print(f'{a.module_id} enabled={a.cmd=="enable"}')
    elif a.cmd=='theme':
        with connect(a.database) as c: set_theme(c,a.module_id,a.theme)
        print(f'{a.module_id} theme={a.theme}')
    return 0
if __name__=='__main__': raise SystemExit(main())
