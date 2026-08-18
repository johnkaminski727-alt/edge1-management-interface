#!/usr/bin/env python3
"""Operator CLI for Edge1 SNMP inventory, MIBs, discovery, alerts and search."""
from __future__ import annotations
import argparse,asyncio,json,shutil,subprocess
from edge1_snmp_platform import connect_db,list_devices
from edge1_snmp_services import AlertEngine,DiscoveryService,MIBService,ensure_extended_schema,get_topology,search_all
def out(value): print(json.dumps(value,sort_keys=True,indent=2,default=str))
def main():
 p=argparse.ArgumentParser(prog='edge1-snmp'); sub=p.add_subparsers(dest='cmd',required=True); oid=sub.add_parser('oid'); oid_sub=oid.add_subparsers(dest='oid_cmd',required=True)
 for name in ('lookup','describe','search'): q=oid_sub.add_parser(name); q.add_argument('value')
 mib=sub.add_parser('mib'); mib_sub=mib.add_subparsers(dest='mib_cmd',required=True); mib_sub.add_parser('list'); imp=mib_sub.add_parser('import'); imp.add_argument('module'); val=mib_sub.add_parser('validate'); val.add_argument('module')
 disc=sub.add_parser('discovery'); disc.add_argument('cidr'); disc.add_argument('--credential-reference',required=True); disc.add_argument('--execute',action='store_true'); disc.add_argument('--concurrency',type=int,default=16); sub.add_parser('devices'); sub.add_parser('alerts-evaluate'); sub.add_parser('topology'); s=sub.add_parser('search'); s.add_argument('query'); args=p.parse_args(); conn=connect_db(); ensure_extended_schema(conn)
 try:
  if args.cmd=='oid':
   svc=MIBService(conn); out((svc.lookup(args.value) or {'found':False,'query':args.value}) if args.oid_cmd in ('lookup','describe') else {'results':svc.search(args.value)})
  elif args.cmd=='mib':
   svc=MIBService(conn)
   if args.mib_cmd=='list': out({'imports':[dict(r) for r in conn.execute('SELECT * FROM mib_imports ORDER BY imported_at DESC')]})
   elif args.mib_cmd=='import': out(svc.import_net_snmp_module(args.module))
   else:
    exe=shutil.which('snmptranslate')
    if not exe: raise SystemExit('snmptranslate is not installed')
    cp=subprocess.run([exe,'-m',f'+{args.module}','-Tp'],capture_output=True,text=True,timeout=120,check=False,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin'}); out({'module':args.module,'valid':cp.returncode==0,'detail':(cp.stderr or cp.stdout)[-4000:]}); return 0 if cp.returncode==0 else 2
  elif args.cmd=='discovery': out(asyncio.run(DiscoveryService().scan(args.cidr,args.credential_reference,dry_run=not args.execute,concurrency=args.concurrency)))
  elif args.cmd=='devices': out({'devices':list_devices(conn)})
  elif args.cmd=='alerts-evaluate': out(AlertEngine(conn).evaluate())
  elif args.cmd=='topology': out(get_topology(conn))
  elif args.cmd=='search': out(search_all(conn,args.query))
  return 0
 finally: conn.close()
if __name__=='__main__': raise SystemExit(main())
