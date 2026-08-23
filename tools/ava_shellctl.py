#!/usr/bin/env python3
"""Enable or disable Ava's attended unrestricted shell gates."""
from __future__ import annotations
import argparse, json, os, tempfile, time
from pathlib import Path

GATE_DIR=Path("/var/lib/wwcx-ava-operator-broker/shell-gates")
AUDIT=Path("/var/log/wwcx-ava-operator-broker/audit.jsonl")
HOSTS={"edge1","business159"}

def require_root():
    if os.geteuid()!=0: raise SystemExit("ava-shellctl must run as root")

def path(host:str)->Path: return GATE_DIR/f"{host}.json"

def audit(event:str, **fields):
    AUDIT.parent.mkdir(parents=True,exist_ok=True)
    record={"time_unix":int(time.time()),"event":event,**fields}
    with AUDIT.open("a",encoding="utf-8") as h: h.write(json.dumps(record,separators=(",",":"),sort_keys=True)+"\n")

def status(host:str):
    p=path(host); now=int(time.time())
    try: value=json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError: return {"host":host,"enabled":False,"reason":"not_enabled"}
    except Exception: return {"host":host,"enabled":False,"reason":"invalid_gate"}
    expires=value.get("expires_at_unix")
    enabled=isinstance(expires,int) and expires>now
    return {"host":host,"enabled":enabled,"reason":"enabled" if enabled else "expired","expires_at_unix":expires if isinstance(expires,int) else None,"remaining_seconds":max(0,expires-now) if isinstance(expires,int) else 0,"actor":str(value.get("actor",""))[:128],"ticket":str(value.get("ticket",""))[:128]}

def enable(host:str, minutes:int, actor:str, reason:str, ticket:str):
    if minutes<1 or minutes>240: raise SystemExit("minutes must be between 1 and 240")
    GATE_DIR.mkdir(parents=True,exist_ok=True); os.chmod(GATE_DIR,0o700)
    now=int(time.time()); value={"version":1,"host":host,"enabled_at_unix":now,"expires_at_unix":now+minutes*60,"actor":actor[:128],"reason":reason[:500],"ticket":ticket[:128]}
    fd,tmp=tempfile.mkstemp(prefix=f".{host}.",dir=GATE_DIR); os.fchmod(fd,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as h: json.dump(value,h,separators=(",",":"),sort_keys=True); h.write("\n")
    os.replace(tmp,path(host)); os.chmod(path(host),0o600)
    audit("shell_gate_enabled",host=host,actor=actor[:128],expires_at_unix=value["expires_at_unix"],ticket=ticket[:128])
    return status(host)

def disable(host:str, actor:str):
    try: path(host).unlink()
    except FileNotFoundError: pass
    audit("shell_gate_disabled",host=host,actor=actor[:128])
    return status(host)

def main():
    require_root(); p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    e=sub.add_parser("enable"); e.add_argument("host",choices=sorted(HOSTS)); e.add_argument("--minutes",type=int,default=15); e.add_argument("--actor",required=True); e.add_argument("--reason",required=True); e.add_argument("--ticket",default="")
    d=sub.add_parser("disable"); d.add_argument("host",choices=sorted(HOSTS)); d.add_argument("--actor",required=True)
    st=sub.add_parser("status"); st.add_argument("host",choices=sorted(HOSTS),nargs="?")
    a=p.parse_args()
    if a.cmd=="enable": result=enable(a.host,a.minutes,a.actor,a.reason,a.ticket)
    elif a.cmd=="disable": result=disable(a.host,a.actor)
    else: result=status(a.host) if a.host else [status(h) for h in sorted(HOSTS)]
    print(json.dumps(result,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
