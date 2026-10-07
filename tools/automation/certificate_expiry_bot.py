#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
STATUS=Path('/var/www/edge1-status/certificate-expiry/status.json'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
def certs():
    rows=[]; now=datetime.now(timezone.utc)
    for p in sorted(Path('/etc/letsencrypt/live').glob('*/fullchain.pem')):
        q=subprocess.run(['openssl','x509','-in',str(p),'-noout','-enddate','-subject'],text=True,capture_output=True,check=False)
        if q.returncode: continue
        vals={}
        for line in q.stdout.splitlines():
            if '=' in line: k,v=line.split('=',1); vals[k.strip()]=v.strip()
        try: exp=datetime.strptime(vals['notAfter'],'%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc); days=(exp-now).total_seconds()/86400
        except Exception: exp=None; days=None
        rows.append({'name':p.parent.name,'expires_at':exp.isoformat() if exp else None,'days_remaining':round(days,1) if days is not None else None,'state':'critical' if days is not None and days<14 else 'warning' if days is not None and days<30 else 'healthy'})
    return rows
def openpgp():
    home=Path('/var/lib/wwcx-openpgp/gnupg')
    if not home.is_dir(): return []
    q=subprocess.run(['gpg','--homedir',str(home),'--with-colons','--list-keys'],text=True,capture_output=True,check=False)
    rows=[]; now=datetime.now(timezone.utc).timestamp()
    for line in q.stdout.splitlines():
        f=line.split(':')
        if f and f[0] in {'pub','sub'} and len(f)>6:
            try: exp=int(f[6] or 0)
            except ValueError: exp=0
            rows.append({'kind':f[0],'key_id':f[4][-16:] if len(f)>4 else None,'expires_at':datetime.fromtimestamp(exp,timezone.utc).isoformat() if exp else None,'days_remaining':round((exp-now)/86400,1) if exp else None,'state':'non_expiring' if not exp else 'critical' if exp-now<14*86400 else 'warning' if exp-now<30*86400 else 'healthy'})
    return rows
def build():
    c=certs(); p=openpgp(); attention=[x for x in [*c,*p] if x.get('state') in {'warning','critical'}]
    return {'contract':'wwcx.certificate-expiry.v1','generated_at':utcnow(),'state':'attention' if attention else 'healthy','certificates':c,'openpgp_keys':p,'attention_count':len(attention),'private_key_material_exposed':False}
def md(d):
    lines=['# Certificate & Key Expiry Monitor','',f"Generated: {d['generated_at']}",'', '## TLS certificates','']
    lines += [f"- **{x['name']}** — {x['days_remaining']} days remaining — {x['state']}" for x in d['certificates']] or ['- None discovered.']
    lines += ['','## OpenPGP public metadata','']+[f"- {x['kind']} `{x['key_id']}` — {x['days_remaining'] if x['days_remaining'] is not None else 'no'} days remaining — {x['state']}" for x in d['openpgp_keys']]
    lines += ['','No private key material is included.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/certificate-expiry/current.md','Certificate & Key Expiry Monitor',md(d)); print(json.dumps({'state':d['state'],'certificates':len(d['certificates']),'attention':d['attention_count']},sort_keys=True))
if __name__=='__main__': main()
