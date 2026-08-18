#!/usr/bin/env python3
"""Extended discovery, MIB, alerting, topology and search services for Edge1 SNMP."""
from __future__ import annotations
import asyncio,json,re,shutil,sqlite3,subprocess,uuid
from typing import Any
from edge1_snmp_platform import NetSNMP,STANDARD_OIDS,allowed_discovery_hosts,canonical_oid,load_config,utcnow

INTERFACE_OIDS={"ifDescr":"1.3.6.1.2.1.2.2.1.2","ifType":"1.3.6.1.2.1.2.2.1.3","ifSpeed":"1.3.6.1.2.1.2.2.1.5","ifAdminStatus":"1.3.6.1.2.1.2.2.1.7","ifOperStatus":"1.3.6.1.2.1.2.2.1.8","ifInOctets":"1.3.6.1.2.1.2.2.1.10","ifInErrors":"1.3.6.1.2.1.2.2.1.14","ifOutOctets":"1.3.6.1.2.1.2.2.1.16","ifOutErrors":"1.3.6.1.2.1.2.2.1.20","ifName":"1.3.6.1.2.1.31.1.1.1.1","ifHighSpeed":"1.3.6.1.2.1.31.1.1.1.15","ifHCInOctets":"1.3.6.1.2.1.31.1.1.1.6","ifHCOutOctets":"1.3.6.1.2.1.31.1.1.1.10","ifAlias":"1.3.6.1.2.1.31.1.1.1.18"}

def ensure_extended_schema(conn):
 conn.executescript("""
 CREATE TABLE IF NOT EXISTS interfaces (device_id TEXT NOT NULL,if_index INTEGER NOT NULL,if_name TEXT,if_descr TEXT,if_alias TEXT,if_type INTEGER,admin_status INTEGER,oper_status INTEGER,speed_bps INTEGER,last_seen TEXT NOT NULL,metadata_json TEXT NOT NULL DEFAULT '{}',PRIMARY KEY(device_id,if_index),FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE CASCADE);
 CREATE TABLE IF NOT EXISTS poll_profiles (profile_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,interval_seconds INTEGER NOT NULL,timeout_seconds INTEGER NOT NULL,retries INTEGER NOT NULL,oid_groups_json TEXT NOT NULL,concurrency_limit INTEGER,enabled INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS alert_policies (policy_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,condition_type TEXT NOT NULL,severity TEXT NOT NULL,threshold REAL,duration_seconds INTEGER NOT NULL DEFAULT 0,cooldown_seconds INTEGER NOT NULL DEFAULT 300,device_scope_json TEXT NOT NULL DEFAULT '[]',tag_scope_json TEXT NOT NULL DEFAULT '[]',notification_policy TEXT,auto_remediation_policy TEXT,enabled INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS alert_state (policy_id TEXT NOT NULL,device_id TEXT NOT NULL,first_true_at TEXT,last_true_at TEXT,last_alert_at TEXT,suppressed_until TEXT,active_alert_id TEXT,PRIMARY KEY(policy_id,device_id));
 CREATE TABLE IF NOT EXISTS topology_links (link_id TEXT PRIMARY KEY,local_device_id TEXT NOT NULL,local_if_index INTEGER,remote_device_id TEXT,remote_identifier TEXT,remote_port TEXT,evidence_type TEXT NOT NULL,confidence TEXT NOT NULL,observed_at TEXT NOT NULL,evidence_json TEXT NOT NULL DEFAULT '{}');
 CREATE INDEX IF NOT EXISTS idx_topology_local ON topology_links(local_device_id);
 CREATE TABLE IF NOT EXISTS mib_imports (import_id TEXT PRIMARY KEY,imported_at TEXT NOT NULL,source_path TEXT,module TEXT,status TEXT NOT NULL,object_count INTEGER NOT NULL DEFAULT 0,detail TEXT NOT NULL DEFAULT '');
 """); conn.commit()
def _suffix_index(oid,base):
 oid=oid.lstrip("."); prefix=base.lstrip(".")+"."
 if not oid.startswith(prefix): return None
 suffix=oid[len(prefix):]; return int(suffix) if suffix.isdigit() else None
def parse_integer(value):
 m=re.search(r"(-?\d+)",value or ""); return int(m.group(1)) if m else None
def discover_interfaces(net,device):
 by_index={}
 for name,base in INTERFACE_OIDS.items():
  values=net.query("snmpbulkwalk",device["management_address"],int(device["snmp_port"]),device["credential_reference"],[base])
  for oid,value in values.items():
   idx=_suffix_index(oid,base)
   if idx is not None: by_index.setdefault(idx,{"if_index":idx})[name]=value
 rows=[]
 for idx,row in sorted(by_index.items()):
  speed=parse_integer(row.get("ifHighSpeed","")); speed=speed*1000000 if speed is not None else parse_integer(row.get("ifSpeed",""))
  rows.append({"if_index":idx,"if_name":row.get("ifName"),"if_descr":row.get("ifDescr"),"if_alias":row.get("ifAlias"),"if_type":parse_integer(row.get("ifType","")),"admin_status":parse_integer(row.get("ifAdminStatus","")),"oper_status":parse_integer(row.get("ifOperStatus","")),"speed_bps":speed,"counters":{k:parse_integer(row.get(k,"")) for k in ("ifHCInOctets","ifHCOutOctets","ifInOctets","ifOutOctets","ifInErrors","ifOutErrors")}})
 return rows
def sync_interfaces(conn,device_id,rows):
 ensure_extended_schema(conn); now=utcnow()
 for row in rows:
  conn.execute("""INSERT INTO interfaces(device_id,if_index,if_name,if_descr,if_alias,if_type,admin_status,oper_status,speed_bps,last_seen,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(device_id,if_index) DO UPDATE SET if_name=excluded.if_name,if_descr=excluded.if_descr,if_alias=excluded.if_alias,if_type=excluded.if_type,admin_status=excluded.admin_status,oper_status=excluded.oper_status,speed_bps=excluded.speed_bps,last_seen=excluded.last_seen""",(device_id,row["if_index"],row.get("if_name"),row.get("if_descr"),row.get("if_alias"),row.get("if_type"),row.get("admin_status"),row.get("oper_status"),row.get("speed_bps"),now,"{}"))
  for name,value in row.get("counters",{}).items():
   if value is not None:
    base=INTERFACE_OIDS[name]; conn.execute("INSERT INTO metrics(ts,device_id,oid,name,value_num,value_text,unit,source) VALUES(?,?,?,?,?,?,?,?)",(now,device_id,f"{base}.{row['if_index']}",name,float(value),None,"octets" if "Octets" in name else "count","interface-poll"))
 conn.commit(); return len(rows)

class DiscoveryService:
 def __init__(self,net=None): self.net=net or NetSNMP()
 async def scan(self,cidr,profile_reference,*,config=None,dry_run=False,concurrency=16):
  config=config or load_config(); hosts=allowed_discovery_hosts(cidr,config)
  if dry_run: return {"dry_run":True,"cidr":cidr,"hosts":hosts,"count":len(hosts)}
  sem=asyncio.Semaphore(max(1,min(concurrency,64)))
  async def probe(host):
   async with sem:
    try:
     result=await asyncio.to_thread(self.net.query,"snmpget",host,161,profile_reference,[STANDARD_OIDS[k] for k in ("sysDescr","sysName","sysObjectID","sysLocation","sysContact")])
     return {"management_address":host,"snmp_capable":True,"snmp_version":"3","credential_reference":profile_reference,"sysDescr":result.get(STANDARD_OIDS["sysDescr"]),"sysName":result.get(STANDARD_OIDS["sysName"]),"sysObjectID":result.get(STANDARD_OIDS["sysObjectID"]),"sysLocation":result.get(STANDARD_OIDS["sysLocation"]),"sysContact":result.get(STANDARD_OIDS["sysContact"])}
    except Exception as exc: return {"management_address":host,"snmp_capable":False,"error":str(exc)[:500]}
  results=await asyncio.gather(*(probe(h) for h in hosts)); return {"dry_run":False,"cidr":cidr,"count":len(results),"devices":results}

class MIBService:
 def __init__(self,conn): self.conn=conn; ensure_extended_schema(conn)
 def upsert_object(self,*,oid,name,module=None,syntax=None,access=None,status=None,units=None,description=None,enums=None):
  oid=canonical_oid(oid); self.conn.execute("""INSERT INTO mib_objects(oid,name,module,syntax,access,status,units,description,enums_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(oid) DO UPDATE SET name=excluded.name,module=excluded.module,syntax=excluded.syntax,access=excluded.access,status=excluded.status,units=excluded.units,description=excluded.description,enums_json=excluded.enums_json,updated_at=excluded.updated_at""",(oid,name,module,syntax,access,status,units,description,json.dumps(enums or {},sort_keys=True),utcnow())); self.conn.commit()
 def lookup(self,value):
  row=self.conn.execute("SELECT * FROM mib_objects WHERE oid=?",(canonical_oid(value),)).fetchone() if re.fullmatch(r"\.?\d+(?:\.\d+)+",value.strip()) else self.conn.execute("SELECT * FROM mib_objects WHERE name=? COLLATE NOCASE LIMIT 1",(value.strip(),)).fetchone(); return dict(row) if row else None
 def search(self,query,limit=100):
  like=f"%{query[:200]}%"; return [dict(r) for r in self.conn.execute("SELECT * FROM mib_objects WHERE oid LIKE ? OR name LIKE ? OR module LIKE ? OR description LIKE ? ORDER BY oid LIMIT ?",(like,like,like,like,min(500,max(1,limit))))]
 def import_net_snmp_module(self,module,*,mib_dirs=None):
  if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",module): raise ValueError("invalid MIB module name")
  exe=shutil.which("snmptranslate")
  if not exe: raise RuntimeError("snmptranslate is not installed")
  env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin"}
  if mib_dirs: env["MIBDIRS"]=":".join(mib_dirs)
  cp=subprocess.run([exe,"-m",f"+{module}","-Tz"],capture_output=True,text=True,timeout=120,env=env,check=False); import_id=str(uuid.uuid4())
  if cp.returncode!=0:
   detail=(cp.stderr or cp.stdout)[-4000:]; self.conn.execute("INSERT INTO mib_imports VALUES(?,?,?,?,?,?,?)",(import_id,utcnow(),None,module,"failed",0,detail)); self.conn.commit(); raise RuntimeError(detail)
  count=0
  for line in cp.stdout.splitlines():
   m=re.match(r'^"([^"]+)"\s+"(\d+(?:\.\d+)+)"',line.strip())
   if m: self.upsert_object(oid=m.group(2),name=m.group(1),module=module); count+=1
  self.conn.execute("INSERT INTO mib_imports VALUES(?,?,?,?,?,?,?)",(import_id,utcnow(),None,module,"succeeded",count,"")); self.conn.commit(); return {"import_id":import_id,"module":module,"status":"succeeded","object_count":count}

class AlertEngine:
 def __init__(self,conn): self.conn=conn; ensure_extended_schema(conn)
 def ensure_default_policies(self):
  now=utcnow(); defaults=[("device-unreachable","Device unreachable","device_unreachable","critical",None,60,600),("snmp-auth-failure","SNMP authentication failure","snmp_auth_failure","warning",None,0,900),("interface-down","Interface down","interface_down","warning",None,60,600),("interface-errors","Excessive interface errors","interface_errors","warning",100.0,300,900)]
  for pid,name,cond,sev,threshold,duration,cooldown in defaults: self.conn.execute("INSERT OR IGNORE INTO alert_policies(policy_id,display_name,condition_type,severity,threshold,duration_seconds,cooldown_seconds,updated_at) VALUES(?,?,?,?,?,?,?,?)",(pid,name,cond,sev,threshold,duration,cooldown,now))
  self.conn.commit()
 def _open_alert(self,policy,device_id,summary,evidence):
  existing=self.conn.execute("SELECT alert_id FROM alerts WHERE device_id=? AND policy=? AND state='open' LIMIT 1",(device_id,policy["policy_id"])).fetchone(); now=utcnow()
  if existing: self.conn.execute("UPDATE alerts SET updated_at=?,summary=?,evidence_json=? WHERE alert_id=?",(now,summary,json.dumps(evidence,sort_keys=True),existing["alert_id"])); self.conn.commit(); return existing["alert_id"]
  alert_id=str(uuid.uuid4()); correlation_id=str(uuid.uuid4()); self.conn.execute("INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?,?)",(alert_id,now,now,None,device_id,policy["severity"],policy["policy_id"],"open",summary,json.dumps(evidence,sort_keys=True),correlation_id)); self.conn.commit(); return alert_id
 def evaluate(self):
  self.ensure_default_policies(); opened=[]; policies={r["condition_type"]:r for r in self.conn.execute("SELECT * FROM alert_policies WHERE enabled=1")}
  for device in self.conn.execute("SELECT device_id,display_name,status,last_error,last_success FROM devices"):
   if device["status"]=="offline" and "device_unreachable" in policies: opened.append(self._open_alert(policies["device_unreachable"],device["device_id"],f"{device['display_name']} is unreachable",[{"type":"device_status","status":device["status"],"last_success":device["last_success"]}]))
   err=(device["last_error"] or "").lower()
   if any(x in err for x in ("authentication","unknown user","wrong digest","authorization")) and "snmp_auth_failure" in policies: opened.append(self._open_alert(policies["snmp_auth_failure"],device["device_id"],f"SNMP authentication failed for {device['display_name']}",[{"type":"poll_error","detail":device["last_error"][:500]}]))
  if "interface_down" in policies:
   for row in self.conn.execute("SELECT device_id,if_index,if_name,if_descr,admin_status,oper_status FROM interfaces WHERE admin_status=1 AND oper_status<>1"): opened.append(self._open_alert(policies["interface_down"],row["device_id"],f"Interface {row['if_name'] or row['if_descr'] or row['if_index']} is down",[{"type":"interface","if_index":row["if_index"],"admin_status":row["admin_status"],"oper_status":row["oper_status"]}]))
  return {"evaluated_at":utcnow(),"active_or_updated":opened,"count":len(opened)}

def search_all(conn,query,limit=100):
 ensure_extended_schema(conn); query=query.strip()[:200]; like=f"%{query}%"; cap=min(200,max(1,limit)); devices=[dict(r) for r in conn.execute("SELECT device_id,display_name,hostname,management_address,vendor,model,serial_number,site,location,status FROM devices WHERE display_name LIKE ? OR hostname LIKE ? OR management_address LIKE ? OR vendor LIKE ? OR model LIKE ? OR serial_number LIKE ? OR site LIKE ? OR location LIKE ? LIMIT ?",(like,like,like,like,like,like,like,like,cap))]; interfaces=[dict(r) for r in conn.execute("SELECT * FROM interfaces WHERE if_name LIKE ? OR if_descr LIKE ? OR if_alias LIKE ? LIMIT ?",(like,like,like,cap))]; mibs=[dict(r) for r in conn.execute("SELECT oid,name,module,description FROM mib_objects WHERE oid LIKE ? OR name LIKE ? OR module LIKE ? OR description LIKE ? LIMIT ?",(like,like,like,like,cap))]; events=[dict(r) for r in conn.execute("SELECT event_id,ts,source_address,trap_oid,severity,event_type,correlation_id FROM events WHERE source_address LIKE ? OR trap_oid LIKE ? OR event_type LIKE ? OR correlation_id LIKE ? LIMIT ?",(like,like,like,like,cap))]; return {"devices":devices,"interfaces":interfaces,"mibs":mibs,"events":events}
def add_topology_link(conn,*,local_device_id,local_if_index,remote_device_id,remote_identifier,remote_port,evidence_type,confidence,evidence):
 ensure_extended_schema(conn)
 if confidence not in {"confirmed","inferred"}: raise ValueError("confidence must be confirmed or inferred")
 link_id=str(uuid.uuid4()); conn.execute("INSERT INTO topology_links VALUES(?,?,?,?,?,?,?,?,?,?)",(link_id,local_device_id,local_if_index,remote_device_id,remote_identifier,remote_port,evidence_type,confidence,utcnow(),json.dumps(evidence,sort_keys=True))); conn.commit(); return link_id
def get_topology(conn):
 ensure_extended_schema(conn); return {"nodes":[dict(r) for r in conn.execute("SELECT device_id,display_name,management_address,device_type,vendor,model,status FROM devices ORDER BY display_name")],"links":[dict(r) for r in conn.execute("SELECT * FROM topology_links ORDER BY observed_at DESC")],"generated_at":utcnow()}
def prune_retention(conn,config=None):
 config=config or load_config(); retention=config.get("retention",{}); deleted={}
 for table,key,default in (("metrics","telemetry_days",30),("events","events_days",90),("audit","audit_days",365)):
  days=max(1,int(retention.get(key,default))); cur=conn.execute(f"DELETE FROM {table} WHERE ts < datetime('now', ?)",(f"-{days} days",)); deleted[table]=cur.rowcount
 conn.commit(); return deleted
