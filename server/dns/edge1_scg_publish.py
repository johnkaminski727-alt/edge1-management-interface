#!/usr/bin/env python3
"""Bounded Spirit Creek Gardens reconciliation; never deletes records or changes MX."""
import argparse,base64,fcntl,json,pathlib,re,subprocess,time
from datetime import datetime,timezone
ZONE='spiritcreekgardens.com'
STATE=pathlib.Path('/var/lib/edge1-dyn')
CONFIG=STATE/'zones'/f'{ZONE}.json'
NSS=['ns1194.dns.dyn.com','ns2150.dns.dyn.com','ns3190.dns.dyn.com','ns4142.dns.dyn.com']
KEY=pathlib.Path('/etc/edge1-secrets/dyn/wwcx-tsig.key')
ALLOWED={(ZONE,'TXT'),('mail.'+ZONE,'A'),('_dmarc.'+ZONE,'TXT'),('edge1-202610._domainkey.'+ZONE,'TXT')}
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def query(ns,name,typ):
 r=subprocess.run(['dig','@'+ns,'+time=2','+tries=1',name,typ,'+noall','+comments','+answer'],text=True,capture_output=True,timeout=5)
 if r.returncode or not re.search(r'status: (NOERROR|NXDOMAIN)',r.stdout):raise RuntimeError('DNS query failed: '+ns)
 vals=[]
 for line in r.stdout.splitlines():
  if line.startswith(';') or not line.strip():continue
  parts=line.split(None,4)
  if len(parts)!=5 or parts[3]!=typ:continue
  vals.append(''.join(re.findall(r'"([^"]*)"',parts[4])) if typ=='TXT' else parts[4])
 return vals
def wire(value):return ' '.join(json.dumps(value[i:i+240]) for i in range(0,len(value),240))
def add(record):
 fields=dict(line.split('\t',1) for line in KEY.read_text().splitlines() if '\t' in line)
 secret=fields['Key HMAC'].strip()
 value=wire(record['value']) if record['type']=='TXT' else record['value']
 body=f"server update.dyndns.com\nzone {ZONE}.\nkey {fields['Key Name'].strip()} {secret}\nupdate add {record['name']}. {record['ttl']} {record['type']} {value}\nsend\n"
 r=subprocess.run(['nsupdate'],input=body,text=True,capture_output=True,timeout=15)
 if r.returncode:raise RuntimeError('Dyn update failed: '+(r.stderr+r.stdout).replace(secret,'[redacted]')[:300])
def reconcile(apply=False):
 cfg=json.loads(CONFIG.read_text()); assert cfg['zone']==ZONE and cfg['mx_enabled'] is False
 checks=[]
 for record in cfg['records']:
  if not record['managed']:continue
  assert (record['name'],record['type']) in ALLOWED
  answers={ns:query(ns,record['name'],record['type']) for ns in NSS}
  ok=all(record['value'] in v for v in answers.values())
  conflict=any(any(v!=record['value'] for v in vals if record['type']!='TXT' or record['name']!=ZONE or v.startswith('v=spf1')) for vals in answers.values())
  changed=False
  if not ok and apply and not conflict:
   add(record); changed=True
   for delay in (2,4,8):
    time.sleep(delay); answers={ns:query(ns,record['name'],record['type']) for ns in NSS}
    ok=all(record['value'] in v for v in answers.values())
    if ok:break
  checks.append({'name':record['name'],'type':record['type'],'ok':ok,'conflict':conflict,'changed':changed,'answers':answers})
 payload={'zone':ZONE,'at':now(),'mode':cfg['mode'],'automatic_publish':cfg['automatic_publish'],'mx_enabled':False,'ok':all(c['ok'] and not c['conflict'] for c in checks),'checks':checks}
 temp=STATE/'scg-status.tmp';temp.write_text(json.dumps(payload,indent=2)+'\n');temp.replace(STATE/'scg-status.json')
 with (STATE/'scg-audit.jsonl').open('a') as f:f.write(json.dumps(payload)+'\n')
 return payload
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--scheduled',action='store_true');a=p.parse_args()
 with (STATE/'scg-publisher.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  cfg=json.loads(CONFIG.read_text());result=reconcile(a.apply or (a.scheduled and cfg['automatic_publish']))
  print(json.dumps(result,indent=2));raise SystemExit(0 if result['ok'] else 1)
