#!/usr/bin/env python3
"""One bounded Edge1 SNMP collection, inventory, alerting and retention cycle."""
from __future__ import annotations
import argparse,asyncio,json,os
from pathlib import Path
from edge1_snmp_platform import NetSNMP,connect_db,get_device,load_config,poll_enabled,utcnow
from edge1_snmp_services import AlertEngine,discover_interfaces,ensure_extended_schema,prune_retention,sync_interfaces
async def run_cycle(db,config_path):
 cfg=load_config(config_path); conn=connect_db(db); ensure_extended_schema(conn)
 try:
  poll_results=await poll_enabled(conn,int(cfg.get('polling',{}).get('concurrency',16))); net=NetSNMP(); sem=asyncio.Semaphore(max(1,min(int(cfg.get('polling',{}).get('concurrency',16)),32)))
  async def collect(device_id):
   async with sem:
    device=get_device(conn,device_id)
    if device['status']!='online': return {'device_id':device_id,'status':'skipped_offline'}
    try:
     rows=await asyncio.to_thread(discover_interfaces,net,device); count=sync_interfaces(conn,device_id,rows); return {'device_id':device_id,'status':'ok','interfaces':count}
    except Exception as exc: return {'device_id':device_id,'status':'error','error':str(exc)[:500]}
  interface_results=await asyncio.gather(*(collect(r['device_id']) for r in poll_results)) if poll_results else []; alerts=AlertEngine(conn).evaluate(); retention=prune_retention(conn,cfg); return {'generated_at':utcnow(),'poll':poll_results,'interfaces':interface_results,'alerts':alerts,'retention_deleted':retention}
 finally: conn.close()
def main():
 p=argparse.ArgumentParser(); p.add_argument('--db',type=Path,default=Path(os.environ.get('EDGE1_SNMP_DB','/var/lib/edge1-snmp/snmp.sqlite3'))); p.add_argument('--config',type=Path,default=Path(os.environ.get('EDGE1_SNMP_CONFIG','/etc/edge1-snmp/config.json'))); args=p.parse_args(); result=asyncio.run(run_cycle(args.db,args.config)); print(json.dumps(result,sort_keys=True)); return 0 if all(x.get('status')!='error' for x in result['interfaces']) else 2
if __name__=='__main__': raise SystemExit(main())
