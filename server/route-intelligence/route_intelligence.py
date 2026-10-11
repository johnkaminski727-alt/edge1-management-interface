#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, subprocess, time
from dataclasses import dataclass,asdict
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse

DB=Path('/var/lib/edge1-route-intelligence/routes.sqlite3')
HOST='10.78.0.2';PORT=8140
E164=re.compile(r'^\+[1-9]\d{7,14}$');SIP_URI=re.compile(r'^(?:sip|sips):[^\s]+$',re.I);DOMAIN=re.compile(r'^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\.?$')
@dataclass
class Candidate: kind:str;target:str;priority:int;cost_hint:str;confidence:str;source:str

def normalize_number(raw):
 d=re.sub(r'\D','',raw or '')
 if len(d)==10:d='1'+d
 out='+'+d
 if not E164.fullmatch(out):raise ValueError('invalid_e164')
 return out

def enum_name(number):return '.'.join(reversed(re.sub(r'\D','',number)))+'.e164.arpa'

def parse_naptr(lines):
 out=[]
 for line in lines:
  m=re.match(r'^\s*(\d+)\s+(\d+)\s+"([^"]*)"\s+"([^"]*)"\s+"([^"]*)"\s+(\S+)\.?\s*$',line)
  if m:out.append((int(m.group(1)),int(m.group(2)),m.group(3),m.group(4),m.group(5),m.group(6)))
 return out

def apply_enum_regexp(regexp,number):
 if len(regexp)<3:return None
 sep=regexp[0];parts=regexp.split(sep)
 if len(parts)<4:return None
 try:return re.sub(parts[1],parts[2],number)
 except re.error:return None

def connect():
 DB.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.executescript('''
 CREATE TABLE IF NOT EXISTS peer_routes(id INTEGER PRIMARY KEY,prefix TEXT NOT NULL,target TEXT NOT NULL,priority INTEGER NOT NULL DEFAULT 50,enabled INTEGER NOT NULL DEFAULT 1,label TEXT NOT NULL,cost_hint TEXT NOT NULL DEFAULT 'direct');
 CREATE TABLE IF NOT EXISTS carrier_routes(id INTEGER PRIMARY KEY,prefix TEXT NOT NULL,carrier TEXT NOT NULL,target_template TEXT NOT NULL,priority INTEGER NOT NULL DEFAULT 500,enabled INTEGER NOT NULL DEFAULT 1,cost_hint TEXT NOT NULL DEFAULT 'unknown',quality TEXT NOT NULL DEFAULT 'production');
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,ts INTEGER NOT NULL,number_hash TEXT NOT NULL,candidate_count INTEGER NOT NULL,selected_kind TEXT,selected_source TEXT);
 CREATE TABLE IF NOT EXISTS dns_discoveries(id INTEGER PRIMARY KEY,qname TEXT NOT NULL,rrtype TEXT NOT NULL,rdata TEXT NOT NULL,ttl INTEGER,source TEXT NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,seen_count INTEGER NOT NULL DEFAULT 1,UNIQUE(qname,rrtype,rdata,source));
 CREATE INDEX IF NOT EXISTS dns_discoveries_last_seen_idx ON dns_discoveries(last_seen DESC);
 CREATE TABLE IF NOT EXISTS sip_endpoints(id INTEGER PRIMARY KEY,uri TEXT NOT NULL,domain TEXT NOT NULL,transport TEXT,source TEXT NOT NULL,verification TEXT NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,seen_count INTEGER NOT NULL DEFAULT 1,UNIQUE(uri,source));
 CREATE INDEX IF NOT EXISTS sip_endpoints_domain_idx ON sip_endpoints(domain,last_seen DESC);
 CREATE TABLE IF NOT EXISTS lookup_history(id INTEGER PRIMARY KEY,ts INTEGER NOT NULL,kind TEXT NOT NULL,input_value TEXT NOT NULL,status TEXT NOT NULL,result_count INTEGER NOT NULL,latency_ms INTEGER NOT NULL);
 ''')
 if c.execute('SELECT count(*) FROM carrier_routes').fetchone()[0]==0:c.execute("INSERT INTO carrier_routes(prefix,carrier,target_template,priority,cost_hint,quality) VALUES(?,?,?,?,?,?)",('+1','telnyx','PJSIP/{digits}@telnyx',900,'provider_rate','production'))
 c.commit();return c

def dns_query(qname,rrtype,timeout=3):
 start=time.monotonic()
 try:p=subprocess.run(['/usr/bin/dig','+time=2','+tries=1','+noall','+answer',rrtype,qname],capture_output=True,text=True,timeout=timeout,check=False)
 except Exception:return [],int((time.monotonic()-start)*1000),'error'
 rows=[]
 if p.returncode==0:
  for line in p.stdout.splitlines():
   parts=line.split(None,4)
   if len(parts)==5:
    try:ttl=int(parts[1])
    except Exception:ttl=None
    rows.append({'name':parts[0].rstrip('.'),'ttl':ttl,'rrtype':parts[3].upper(),'rdata':parts[4]})
 return rows,int((time.monotonic()-start)*1000),'ok' if p.returncode==0 else 'error'

def store_dns(c,qname,rrtype,rows,source):
 now=int(time.time())
 for r in rows:
  c.execute('''INSERT INTO dns_discoveries(qname,rrtype,rdata,ttl,source,first_seen,last_seen,seen_count) VALUES(?,?,?,?,?,?,?,1)
   ON CONFLICT(qname,rrtype,rdata,source) DO UPDATE SET ttl=excluded.ttl,last_seen=excluded.last_seen,seen_count=seen_count+1''',(qname,rrtype,r['rdata'],r['ttl'],source,now,now))
 c.commit()

def store_endpoint(c,uri,source,verification='dns_verified',transport=None):
 m=re.match(r'^sips?:[^@\s]+@([^;>\s]+)',uri,re.I)
 domain=(m.group(1) if m else uri.split(':',1)[-1]).strip('[]').lower().rstrip('.')
 domain=domain.split(';',1)[0]
 if ':' in domain and domain.rsplit(':',1)[1].isdigit(): domain=domain.rsplit(':',1)[0]
 now=int(time.time())
 c.execute('''INSERT INTO sip_endpoints(uri,domain,transport,source,verification,first_seen,last_seen,seen_count) VALUES(?,?,?,?,?,?,?,1)
  ON CONFLICT(uri,source) DO UPDATE SET domain=excluded.domain,transport=excluded.transport,verification=excluded.verification,last_seen=excluded.last_seen,seen_count=seen_count+1''',(uri,domain,transport,source,verification,now,now));c.commit()
 return domain

def discover_sip_domain(domain,c=None):
 domain=domain.lower().rstrip('.')
 if not DOMAIN.fullmatch(domain):raise ValueError('invalid_domain')
 own=c is None;c=c or connect();start=time.monotonic();allrows=[]
 try:
  for qname,rrtype in [(domain,'NAPTR'),('_sip._udp.'+domain,'SRV'),('_sip._tcp.'+domain,'SRV'),('_sips._tcp.'+domain,'SRV')]:
   rows,lat,status=dns_query(qname,rrtype);store_dns(c,qname,rrtype,rows,'sip_dns');allrows.extend([{'qname':qname,**r} for r in rows])
   if rrtype=='SRV':
    transport='tls' if qname.startswith('_sips._tcp.') else ('tcp' if qname.startswith('_sip._tcp.') else 'udp')
    scheme='sips' if transport=='tls' else 'sip'
    for r in rows:
     p=r['rdata'].split()
     if len(p)>=4 and p[2].isdigit():
      target=p[3].rstrip('.');port=p[2]
      uri=f'{scheme}:{target}:{port}' if transport=='tls' else f'{scheme}:{target}:{port};transport={transport}'
      store_endpoint(c,uri, 'sip_dns_srv', 'dns_verified', transport)
  c.execute('INSERT INTO lookup_history(ts,kind,input_value,status,result_count,latency_ms) VALUES(?,?,?,?,?,?)',(int(time.time()),'sip_dns',domain,'ok',len(allrows),int((time.monotonic()-start)*1000)));c.commit()
  return {'domain':domain,'answers':allrows,'answer_count':len(allrows)}
 finally:
  if own:c.close()

def query_enum(number,timeout=3,c=None):
 own=c is None;c=c or connect();name=enum_name(number);start=time.monotonic();rows,lat,status=dns_query(name,'NAPTR',timeout);store_dns(c,name,'NAPTR',rows,'public_enum_e164_arpa');out=[]
 for r in rows:
  parsed=parse_naptr([r['rdata']])
  for order,pref,flags,service,regexp,replacement in parsed:
   if 'e2u+sip' not in service.lower() and 'e2u+sips' not in service.lower():continue
   uri=apply_enum_regexp(regexp,number) if regexp else None;target=uri or (replacement if replacement!='.' else '')
   if target and SIP_URI.match(target):
    out.append(Candidate('enum_sip',target,100+order,'potentially direct/free','dns_verified','e164.arpa'))
    domain=store_endpoint(c,target,'public_enum_e164_arpa')
    if DOMAIN.fullmatch(domain):
     try:discover_sip_domain(domain,c)
     except ValueError:pass
 c.execute('INSERT INTO lookup_history(ts,kind,input_value,status,result_count,latency_ms) VALUES(?,?,?,?,?,?)',(int(time.time()),'enum',hashlib.sha256(number.encode()).hexdigest(),status,len(out),int((time.monotonic()-start)*1000)));c.commit()
 if own:c.close()
 return sorted(out,key=lambda x:x.priority)

def peer_candidates(c,number):
 digits=number[1:];out=[]
 for r in c.execute('SELECT * FROM peer_routes WHERE enabled=1 ORDER BY priority,prefix DESC'):
  p=r['prefix'].lstrip('+')
  if digits.startswith(p):out.append(Candidate('trusted_peer',r['target'].format(e164=number,digits=digits),r['priority'],r['cost_hint'],'configured',r['label']))
 return out

def carrier_candidates(c,number):
 digits=number[1:];out=[]
 for r in c.execute('SELECT * FROM carrier_routes WHERE enabled=1 ORDER BY priority'):
  if number.startswith(r['prefix']):out.append(Candidate('carrier',r['target_template'].format(e164=number,digits=digits),r['priority'],r['cost_hint'],r['quality'],r['carrier']))
 return out

def resolve(number,do_enum=True):
 n=normalize_number(number)
 with connect() as c:
  candidates=peer_candidates(c,n)
  if do_enum:candidates+=query_enum(n,c=c)
  candidates+=carrier_candidates(c,n);candidates.sort(key=lambda x:x.priority)
  selected=candidates[0] if candidates else None
  c.execute('INSERT INTO audit(ts,number_hash,candidate_count,selected_kind,selected_source) VALUES(?,?,?,?,?)',(int(time.time()),hashlib.sha256(n.encode()).hexdigest(),len(candidates),selected.kind if selected else None,selected.source if selected else None));c.commit()
 return {'contract':'wwcx.route-intelligence.v2','number':n,'mode':'resolution_only','execution_authorized':False,'policy_order':['trusted_peer','enum_sip','carrier'],'candidates':[asdict(x) for x in candidates],'selected':asdict(selected) if selected else None,'generated_at':int(time.time())}

def stats():
 with connect() as c:
  return {'dns_discoveries':c.execute('SELECT count(*) FROM dns_discoveries').fetchone()[0],'sip_endpoints':c.execute('SELECT count(*) FROM sip_endpoints').fetchone()[0],'lookup_history':c.execute('SELECT count(*) FROM lookup_history').fetchone()[0]}

class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,code,obj):
  b=json.dumps(obj,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/healthz':return self.sendj(200,{'ok':True,'service':'route-intelligence','mode':'resolution_only','database':stats()})
  if p.path=='/v1/resolve':
   q=parse_qs(p.query);raw=(q.get('number')or[''])[0];enum=(q.get('enum')or['1'])[0]!='0'
   try:return self.sendj(200,resolve(raw,enum))
   except ValueError as e:return self.sendj(400,{'error':str(e)})
  if p.path=='/v1/discover':
   domain=(parse_qs(p.query).get('domain')or[''])[0]
   try:return self.sendj(200,{'contract':'wwcx.sip-dns-discovery.v1','mode':'resolution_only','execution_authorized':False,**discover_sip_domain(domain)})
   except ValueError as e:return self.sendj(400,{'error':str(e)})
  if p.path=='/v1/discoveries':
   with connect() as c:
    dns=[dict(r) for r in c.execute('SELECT qname,rrtype,rdata,ttl,source,first_seen,last_seen,seen_count FROM dns_discoveries ORDER BY last_seen DESC LIMIT 200')];sip=[dict(r) for r in c.execute('SELECT uri,domain,transport,source,verification,first_seen,last_seen,seen_count FROM sip_endpoints ORDER BY last_seen DESC LIMIT 200')]
   return self.sendj(200,{'contract':'wwcx.route-discovery-store.v1','dns':dns,'sip_endpoints':sip})
  return self.sendj(404,{'error':'not_found'})

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--test',action='store_true');a=ap.parse_args()
 if a.test:
  assert normalize_number('(780) 298-6143')=='+17802986143';sample=['100 10 "u" "E2U+sip" "!^.*$!sip:test@example.net!" .'];n=parse_naptr(sample);assert len(n)==1 and apply_enum_regexp(n[0][4],'+17802986143')=='sip:test@example.net';connect().close();print('ROUTE_INTELLIGENCE_SELF_TEST_OK');return
 connect().close();ThreadingHTTPServer((HOST,PORT),H).serve_forever()
if __name__=='__main__':main()
