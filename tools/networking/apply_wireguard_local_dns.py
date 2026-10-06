#!/usr/bin/env python3
"""Safely reconcile private WireGuard A/PTR records into Unbound."""
from __future__ import annotations
import argparse,ipaddress,json,os,re,shutil,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path
LABEL_RE=re.compile(r'[^a-z0-9-]+'); ZONE='wg.internal.ww.cx.'
def label(v): return LABEL_RE.sub('-',str(v).lower().strip()).strip('-')[:63] or 'device'
def render(identity):
 lines=['server:',f'    local-zone: "{ZONE}" static']; records=[]
 for d in identity.get('devices') or []:
  if not d.get('registration_id') or d.get('registration_status')=='quarantined': continue
  name=f"{label(d.get('name'))}.{ZONE}"
  for raw in d.get('assigned_addresses') or []:
   ip=str(ipaddress.ip_interface(raw).ip)
   if ':' in ip: continue
   lines += [f'    local-data: "{name} A {ip}"',f'    local-data-ptr: "{ip} {name}"']; records.append({'name':name.rstrip('.'),'address':ip})
 return '\n'.join(lines)+'\n',records
def atomic_text(path,text,mode=0o644):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name('.'+path.name+'.tmp'); tmp.write_text(text); os.chmod(tmp,mode); tmp.replace(path)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--identity',type=Path,default=Path('/var/lib/edge1-operations-api/wireguard-identity.json')); ap.add_argument('--target',type=Path,default=Path('/etc/unbound/unbound.conf.d/edge1-wireguard-local.conf')); ap.add_argument('--status',type=Path,default=Path('/var/www/edge1-status/wireguard-local-dns.json')); ap.add_argument('--check',default='/usr/sbin/unbound-checkconf'); ap.add_argument('--no-reload',action='store_true'); a=ap.parse_args()
 identity=json.loads(a.identity.read_text()); candidate,records=render(identity)
 with tempfile.NamedTemporaryFile('w',prefix='edge1-wg-dns-',suffix='.conf',delete=False) as f: f.write(candidate); cand=Path(f.name)
 try: subprocess.run([a.check,str(cand)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 finally: cand.unlink(missing_ok=True)
 previous=a.target.read_text() if a.target.exists() else None; changed=previous!=candidate
 if changed:
  if a.target.exists(): shutil.copy2(a.target,a.target.with_suffix(a.target.suffix+'.previous'))
  atomic_text(a.target,candidate)
  if not a.no_reload: subprocess.run(['systemctl','reload-or-restart','unbound'],check=True)
 status={'schema_version':1,'contract':'wwcx.wireguard-local-dns.v1','generated_at':datetime.now(timezone.utc).isoformat(),'zone':ZONE,'record_count':len(records),'changed':changed,'records':records}
 atomic_text(a.status,json.dumps(status,indent=2,sort_keys=True)+'\n',0o640)
 print(json.dumps({'ok':True,'record_count':len(records),'changed':changed},sort_keys=True))
if __name__=='__main__':main()
