from __future__ import annotations
import base64,json,os,struct,subprocess,time,grp
from pathlib import Path
LOG=Path('/opt/AdGuardHome/data/querylog.json'); POLICY=Path('/var/lib/edge1-egress/policy.json'); RUNTIME=Path('/var/lib/edge1-egress/runtime.json')

def dns_name(b,o):
 seen=0
 while o<len(b):
  n=b[o]
  if n==0:return o+1
  if n&0xc0==0xc0:return o+2
  o+=1+n;seen+=1
  if seen>128:raise ValueError
 raise ValueError

def a_records(encoded):
 try:b=base64.b64decode(encoded); qd,an=struct.unpack('!HH',b[4:8]);o=12
 except:return []
 try:
  for _ in range(qd):o=dns_name(b,o)+4
  out=[]
  for _ in range(an):
   o=dns_name(b,o);typ,cls,ttl,rdlen=struct.unpack('!HHIH',b[o:o+10]);o+=10;rd=b[o:o+rdlen];o+=rdlen
   if typ==1 and cls==1 and rdlen==4:out.append('.'.join(map(str,rd)))
  return out
 except:return []
def cfg():
 try:
  d=json.loads(POLICY.read_text());return [s for s in d.get('services',[]) if s.get('enabled') and s.get('gateway')=='us']
 except:return []
def match(q,services):
 q=q.lower().rstrip('.')
 for s in services:
  for suffix in s.get('domains',[]):
   x=suffix.lower().rstrip('.')
   if q==x or q.endswith('.'+x):return s['id']
 return None
def add(ip):
 subprocess.run(['nft','add','element','inet','edge1_egress','us4','{',ip,'timeout','6h','}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def write_runtime(counts,last):
 d={'schema':'wwcx.edge1-egress-runtime.v1','updated_at':int(time.time()),'destination_counts':counts,'last_policy_match':last}
 t=RUNTIME.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');os.chown(t,0,grp.getgrnam('wwadmin').gr_gid);os.chmod(t,0o640);os.replace(t,RUNTIME)
def process(line,services,seen,counts):
 try:x=json.loads(line)
 except:return None
 sid=match(str(x.get('QH','')),services)
 if not sid:return None
 for ip in a_records(str(x.get('Answer',''))):
  if ip not in seen: add(ip);seen.add(ip);counts[sid]=counts.get(sid,0)+1
 return sid
def main():
 seen=set();counts={};last=None;RUNTIME.parent.mkdir(parents=True,exist_ok=True)
 while not LOG.exists():time.sleep(2)
 # narrow warm-up: inspect only recent records and retain only configured suffix matches
 size=LOG.stat().st_size;start=max(0,size-4*1024*1024)
 with LOG.open('r',errors='ignore') as f:
  f.seek(start)
  if start:f.readline()
  services=cfg()
  for line in f:
   x=process(line,services,seen,counts);last=x or last
  write_runtime(counts,last)
  while True:
   line=f.readline()
   if not line:
    if LOG.stat().st_size < f.tell(): f.seek(0)
    services=cfg();write_runtime(counts,last);time.sleep(1);continue
   x=process(line,services,seen,counts);last=x or last
if __name__=='__main__':main()
