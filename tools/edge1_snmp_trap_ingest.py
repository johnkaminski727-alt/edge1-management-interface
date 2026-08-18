#!/usr/bin/env python3
"""Normalize snmptrapd traphandle input into the Edge1 SNMP event store."""
from __future__ import annotations
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"server"))
from edge1_snmp_platform import connect_db,normalize_trap,utcnow

def parse_lines(text):
    lines=[line.strip() for line in text.splitlines() if line.strip()]; source=None; varbinds={}; trap_oid=None
    for line in lines:
        if line.startswith("UDP:") or line.startswith("TCP:"): source=line; continue
        if " " in line:
            key,value=line.split(None,1); key=key.lstrip("."); varbinds[key]=value
            if key in {"1.3.6.1.6.3.1.1.4.1.0","SNMPv2-MIB::snmpTrapOID.0"}: trap_oid=value.split()[-1].lstrip(".")
    return {"timestamp":utcnow(),"source_address":source,"trap_oid":trap_oid or "1.3.6.1.6.3.1.1.5.1","event_type":"snmp_trap","varbinds":varbinds,"raw_metadata":{"transport":"snmptrapd-traphandle"}}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--db",type=Path,default=Path(os.environ.get("EDGE1_SNMP_DB","/var/lib/edge1-snmp/snmp.sqlite3"))); args=p.parse_args(); raw=sys.stdin.read(1024*1024)
    if not raw.strip(): raise SystemExit("empty trap payload")
    try:
        payload=json.loads(raw)
        if not isinstance(payload,dict): raise ValueError("JSON trap must be an object")
    except (json.JSONDecodeError,ValueError): payload=parse_lines(raw)
    with connect_db(args.db) as conn: result=normalize_trap(conn,payload)
    print(json.dumps(result,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
