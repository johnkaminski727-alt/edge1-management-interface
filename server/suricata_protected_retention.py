#!/usr/bin/env python3
"""Bounded root-only retention for sanitized Suricata alert summaries."""
from __future__ import annotations
import argparse, contextlib, datetime as dt, fcntl, hashlib, json, os, sqlite3, stat
from pathlib import Path
from typing import Any, Iterable

POLICY_CONTRACT="wwcx.suricata-protected-retention-policy.v1"
SOURCE_SCHEMA="wwcx.suricata-source-alert.v1"
STATUS_SCHEMA="wwcx.suricata-protected-retention-status.v1"
DB_SCHEMA="wwcx.suricata-protected-retention-db.v1"

def now_utc(): return dt.datetime.now(dt.timezone.utc)
def iso(v): return v.astimezone(dt.timezone.utc).isoformat()
def parse_time(v):
    if not isinstance(v,str) or not v.strip(): return None
    try:
        p=dt.datetime.fromisoformat(v.strip().replace("Z","+00:00"))
        return (p if p.tzinfo else p.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)
    except ValueError: return None

def load_policy(path:Path):
    p=json.loads(path.read_text())
    if p.get("contract")!=POLICY_CONTRACT or p.get("status") not in {"implementation_ready","active"}: raise ValueError("invalid policy")
    if p.get("enabled") is not True or p.get("activation_requires_explicit_authorization") is not True: raise ValueError("policy disabled")
    if p.get("acceptance",{}).get("deployment_authorized") is not True: raise ValueError("deployment unauthorized")
    return p

def atomic_json(path:Path,value:dict):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"w") as h:
            json.dump(value,h,indent=2,sort_keys=True); h.write("\n"); h.flush(); os.fsync(h.fileno())
        os.chmod(tmp,0o600); os.replace(tmp,path)
        dfd=os.open(path.parent,os.O_DIRECTORY); os.fsync(dfd); os.close(dfd)
    finally:
        with contextlib.suppress(FileNotFoundError): tmp.unlink()

def private_dir(path:Path):
    path.mkdir(parents=True,exist_ok=True); os.chmod(path,0o700)
    if os.geteuid()==0 and path.stat().st_uid!=0: os.chown(path,0,0)
    if stat.S_IMODE(path.stat().st_mode)!=0o700: raise PermissionError("private directory mode")

def source_node(v:Any):
    if isinstance(v,dict):
        if v.get("alert_schema")==SOURCE_SCHEMA and isinstance(v.get("recent_alerts"),list): return v
        for child in v.values():
            found=source_node(child)
            if found is not None: return found
    elif isinstance(v,list):
        for child in v:
            found=source_node(child)
            if found is not None: return found
    return None

def text(v,n,required=False):
    if v is None:
        if required: raise ValueError("missing text")
        return None
    if not isinstance(v,str) or len(v.strip())>n or (required and not v.strip()): raise ValueError("invalid text")
    return v.strip() or None

def integer(v,lo,hi=None):
    if v is None:return None
    if isinstance(v,bool) or not isinstance(v,int) or v<lo or (hi is not None and v>hi): raise ValueError("invalid integer")
    return v

def normalize_alert(a:Any,allowed:set[str]):
    if not isinstance(a,dict) or set(a)-allowed or any(isinstance(v,(dict,list)) for v in a.values()): raise ValueError("rejected alert")
    stamp=parse_time(text(a.get("timestamp"),128,True))
    if stamp is None: raise ValueError("timestamp")
    sev=integer(a.get("severity"),0,255); supplied=str(a.get("risk","")).lower()
    risk=supplied if supplied in {"critical","high","medium","low","informational","unknown"} else ({1:"critical",2:"high",3:"medium"}.get(sev,"low") if sev is not None else "unknown")
    return {"timestamp":iso(stamp),"signature":text(a.get("signature"),512,True),"severity":sev,"risk":risk,
      "category":text(a.get("category"),256),"action":text(a.get("action"),64),"source":text(a.get("source"),128),
      "source_port":integer(a.get("source_port"),1,65535),"destination":text(a.get("destination"),128),
      "destination_port":integer(a.get("destination_port"),1,65535),"protocol":text(a.get("protocol"),32),
      "application_protocol":text(a.get("application_protocol"),64),"signature_id":integer(a.get("signature_id"),0),
      "generator_id":integer(a.get("generator_id"),0),"revision":integer(a.get("revision"),0),
      "flow_id":integer(a.get("flow_id"),0),"event_id":text(a.get("event_id"),128)}

def event_key(alert:dict,fields:Iterable[str]):
    return hashlib.sha256(json.dumps({f:alert.get(f) for f in fields},sort_keys=True,separators=(",",":")).encode()).hexdigest()
def db_bytes(path): return sum(p.stat().st_size for p in (path,Path(str(path)+"-wal"),Path(str(path)+"-shm")) if p.is_file())

def init_db(c,page_size,max_pages,new):
    c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA secure_delete=ON"); c.execute("PRAGMA journal_mode=DELETE"); c.execute("PRAGMA synchronous=FULL")
    if new:
        c.execute(f"PRAGMA page_size={int(page_size)}"); c.execute("PRAGMA auto_vacuum=INCREMENTAL"); c.execute("VACUUM")
    c.execute(f"PRAGMA max_page_count={int(max_pages)}")
    c.executescript("""CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alerts(event_key TEXT PRIMARY KEY,event_time TEXT NOT NULL,ingested_at TEXT NOT NULL,risk TEXT NOT NULL,signature_id INTEGER,flow_id TEXT,schema_version TEXT NOT NULL,payload_json TEXT NOT NULL) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS alerts_event_time_idx ON alerts(event_time); CREATE INDEX IF NOT EXISTS alerts_risk_idx ON alerts(risk); CREATE INDEX IF NOT EXISTS alerts_signature_id_idx ON alerts(signature_id);
CREATE TABLE IF NOT EXISTS ingest_runs(run_at TEXT PRIMARY KEY,source_generated_at TEXT,accepted_count INTEGER NOT NULL,duplicate_count INTEGER NOT NULL,rejected_count INTEGER NOT NULL,pruned_count INTEGER NOT NULL,retained_count INTEGER NOT NULL,database_bytes INTEGER NOT NULL,state TEXT NOT NULL);""")
    c.execute("INSERT OR REPLACE INTO metadata VALUES('schema_version',?)",(DB_SCHEMA,))

def prune(c,p,current):
    s=p["storage"]; deleted=max(0,c.execute("DELETE FROM alerts WHERE event_time < ?",(iso(current-dt.timedelta(days=int(s["retention_days"]))),)).rowcount)
    excess=max(0,c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]-int(s["max_events"]))
    if excess: deleted+=max(0,c.execute("DELETE FROM alerts WHERE event_key IN (SELECT event_key FROM alerts ORDER BY event_time,event_key LIMIT ?)",(excess,)).rowcount)
    target=int(int(s["max_page_count"])*int(s["prune_target_percent"])/100)
    for _ in range(100):
        used=c.execute("PRAGMA page_count").fetchone()[0]-c.execute("PRAGMA freelist_count").fetchone()[0]
        if used<=target: break
        n=max(0,c.execute("DELETE FROM alerts WHERE event_key IN (SELECT event_key FROM alerts ORDER BY event_time,event_key LIMIT 500)").rowcount); deleted+=n
        if not n: break
    c.execute("PRAGMA incremental_vacuum(256)"); return deleted

def integrity(c): return c.execute("PRAGMA quick_check").fetchone()[0]=="ok"
def existing(db):
    with sqlite3.connect(f"file:{db}?mode=ro",uri=True) as c:
        row=c.execute("SELECT COUNT(*),MIN(event_time),MAX(event_time) FROM alerts").fetchone(); return row[0],row[1],row[2],integrity(c)

def ingest(policy_path:Path,source_override=None,database_override=None,status_override=None,now=None):
    current=(now or now_utc()).astimezone(dt.timezone.utc); p=load_policy(policy_path); s=p["storage"]
    source=source_override or Path(p["ingest"]["source"]); db=database_override or Path(s["database"]); status=status_override or Path(s["status_file"])
    private_dir(db.parent); accepted=duplicates=rejected=pruned=retained=0; oldest=newest=generated=None; state="healthy"; ok=False; error=None
    try:
        lock=(db.parent/".ingest.lock").open("a+"); os.chmod(lock.name,0o600); fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        try: raw=json.loads(source.read_text())
        except (FileNotFoundError,OSError,json.JSONDecodeError) as exc: state="source_unavailable"; error=type(exc).__name__; raise RuntimeError from exc
        node=source_node(raw)
        if node is None: state="schema_rejected"; raise ValueError("source schema")
        t=parse_time(node.get("generated_at") or (raw.get("generated_at") if isinstance(raw,dict) else None)); generated=iso(t) if t else None
        normalized=[]; allowed=set(p["privacy"]["approved_fields"]); fields=p["ingest"]["deduplication"]["canonical_fields"]
        for item in node["recent_alerts"][:int(p["ingest"]["max_alerts_per_run"])]:
            try: n=normalize_alert(item,allowed); normalized.append((event_key(n,fields),n))
            except ValueError: rejected+=1
        with sqlite3.connect(db,timeout=15) as c:
            init_db(c,s["page_size_bytes"],s["max_page_count"],not db.exists())
            with c:
                pruned+=prune(c,p,current)
                for key,item in normalized:
                    payload=json.dumps(item,sort_keys=True,separators=(",",":")); n=c.execute("INSERT OR IGNORE INTO alerts VALUES(?,?,?,?,?,?,?,?)",(key,item["timestamp"],iso(current),item["risk"],item.get("signature_id"),str(item.get("flow_id")) if item.get("flow_id") is not None else None,SOURCE_SCHEMA,payload)).rowcount
                    accepted+=n; duplicates+=1-n
                pruned+=prune(c,p,current); retained,oldest,newest=c.execute("SELECT COUNT(*),MIN(event_time),MAX(event_time) FROM alerts").fetchone()
                if db_bytes(db)>int(s["max_database_bytes"]): state="capacity_limited"
                c.execute("INSERT OR REPLACE INTO ingest_runs VALUES(?,?,?,?,?,?,?,?,?)",(iso(current),generated,accepted,duplicates,rejected,pruned,retained,db_bytes(db),state))
            ok=integrity(c)
        os.chmod(db,0o600); lock.close()
    except RuntimeError: pass
    except ValueError as exc: state="schema_rejected"; error=type(exc).__name__
    except (OSError,sqlite3.DatabaseError,PermissionError) as exc: state="storage_error"; error=type(exc).__name__
    if db.is_file() and (retained==0 or not ok): retained,oldest,newest,ok=existing(db)
    result={"schema_version":STATUS_SCHEMA,"generated_at":iso(current),"state":state,"source_schema":SOURCE_SCHEMA,"source_generated_at":generated,"accepted_count":accepted,"duplicate_count":duplicates,"rejected_count":rejected,"pruned_count":pruned,"retained_count":retained,"database_bytes":db_bytes(db),"oldest_event_time":oldest,"newest_event_time":newest,"integrity_ok":ok,"read_only_source":True,"raw_eve_accessed":False,"traffic_controls_changed":False}
    if error: result["error_type"]=error
    atomic_json(status,result); return result

def query(policy_path:Path,hours:int,limit:int,database_override=None,now=None):
    if os.geteuid()!=0: raise PermissionError("root-only")
    p=load_policy(policy_path)
    if not 1<=hours<=int(p["query"]["max_window_days"])*24 or not 1<=limit<=int(p["query"]["max_limit"]): raise ValueError("query bounds")
    db=database_override or Path(p["storage"]["database"]); cutoff=iso((now or now_utc())-dt.timedelta(hours=hours))
    with sqlite3.connect(f"file:{db}?mode=ro",uri=True) as c: return [json.loads(r[0]) for r in c.execute("SELECT payload_json FROM alerts WHERE event_time>=? ORDER BY event_time DESC,event_key DESC LIMIT ?",(cutoff,limit))]

def verify(policy_path:Path,database_override=None,status_override=None):
    p=load_policy(policy_path); db=database_override or Path(p["storage"]["database"]); status=status_override or Path(p["storage"]["status_file"])
    row_count=0; ok=False
    if db.is_file():
        with sqlite3.connect(f"file:{db}?mode=ro",uri=True) as c: ok=integrity(c); row_count=c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    checks={"database_present":db.is_file(),"status_present":status.is_file(),"database_mode":oct(stat.S_IMODE(db.stat().st_mode)) if db.is_file() else None,"status_mode":oct(stat.S_IMODE(status.stat().st_mode)) if status.is_file() else None,"directory_mode":oct(stat.S_IMODE(db.parent.stat().st_mode)) if db.parent.is_dir() else None,"database_bytes":db_bytes(db),"public_path_absent":all(not x.resolve(strict=False).is_relative_to((Path('/var')/'www').resolve(strict=False)) for x in (db,status)),"integrity_ok":ok,"row_count":row_count}
    checks["ok"]=all((checks["database_present"],checks["status_present"],checks["database_mode"]=="0o600",checks["status_mode"]=="0o600",checks["directory_mode"]=="0o700",checks["public_path_absent"],ok,checks["database_bytes"]<=int(p["storage"]["max_database_bytes"]),row_count<=int(p["storage"]["max_events"])))
    return checks

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--policy",type=Path,required=True); sp=ap.add_subparsers(dest="command",required=True)
    i=sp.add_parser("ingest"); i.add_argument("--source",type=Path); i.add_argument("--database",type=Path); i.add_argument("--status",type=Path)
    q=sp.add_parser("query"); q.add_argument("--hours",type=int,default=24); q.add_argument("--limit",type=int,default=100); q.add_argument("--database",type=Path)
    v=sp.add_parser("verify"); v.add_argument("--database",type=Path); v.add_argument("--status",type=Path); a=ap.parse_args()
    out=ingest(a.policy,a.source,a.database,a.status) if a.command=="ingest" else query(a.policy,a.hours,a.limit,a.database) if a.command=="query" else verify(a.policy,a.database,a.status)
    print(json.dumps(out,indent=2,sort_keys=True)); return 0 if a.command=="query" or out.get("ok") or out.get("state") in {"healthy","capacity_limited"} else 1
if __name__=="__main__": raise SystemExit(main())
