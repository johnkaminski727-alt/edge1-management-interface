#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

STATE = Path('/var/lib/edge1-authoritative-dns')
OUTPUT = Path('/var/www/edge1-status/dns-zone-inventory.json')
NSS = ['ns1194.dns.dyn.com','ns2150.dns.dyn.com','ns3190.dns.dyn.com','ns4142.dns.dyn.com']
RECONCILE = Path('/opt/edge1-management-interface/tools/dns/reconcile_hidden_primary_candidate.py')
MANAGED = Path('/opt/edge1-management-interface/config/dns/managed-zones.json')

def inventory_paths():
    cfg=load_json(MANAGED)
    return [Path(str(z.get('inventory_file'))) for z in cfg.get('zones',[]) if z.get('inventory_file')]

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def load_json(path: Path):
    try: return json.loads(path.read_text())
    except Exception: return {}

def serial(zone: str, ns: str):
    p=subprocess.run(['/usr/bin/dig','+short','+time=4','+tries=1','@'+ns,zone,'SOA'],text=True,capture_output=True,timeout=7)
    parts=p.stdout.split()
    return int(parts[2]) if p.returncode==0 and len(parts)>=3 and parts[2].isdigit() else None

def check(inv_path: Path):
    inv=load_json(inv_path); zone=str(inv.get('zone') or '').rstrip('.')
    zone_file=Path(str(inv.get('candidate_zone_file') or ''))
    result={'zone':zone,'inventory_file':str(inv_path),'zone_file':str(zone_file),'record_count':inv.get('record_count',0),'candidate_soa_serial':inv.get('candidate_soa_serial'),'public_authoritative_provider':inv.get('public_authoritative_provider','Dyn Standard DNS'),'publication_method':inv.get('publication_method','authenticated TSIG/API synchronization'),'mx_cutover_authorized':bool(inv.get('mx_cutover_authorized',False))}
    if not zone or not zone_file.is_file():
        result.update({'status':'invalid','ok':False,'mismatch_count':None,'public_serials':{}}); return result
    digest=hashlib.sha256(zone_file.read_bytes()).hexdigest()
    result['candidate_hash_matches_inventory']=(digest==inv.get('zone_file_sha256'))
    result['public_serials']={ns:serial(zone,ns) for ns in NSS}
    cmd=['/usr/bin/python3',str(RECONCILE),'--zone-file',str(zone_file),'--zone',zone]
    for ns in NSS: cmd += ['--nameserver',ns]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=60)
    try: rec=json.loads(p.stdout)
    except Exception: rec={'ok':False,'mismatch_count':None,'mismatches':[{'error':(p.stderr or p.stdout or 'reconcile failed')[:500]}]}
    result['mismatch_count']=rec.get('mismatch_count'); result['mismatches']=rec.get('mismatches',[])
    serials=[v for v in result['public_serials'].values() if v is not None]
    serial_agree=len(serials)==len(NSS) and len(set(serials))==1
    result['public_serial_agreement']=serial_agree
    result['public_soa_serial']=serials[0] if serial_agree else None
    exact=bool(rec.get('ok')) and result['candidate_hash_matches_inventory'] and serial_agree and result['public_soa_serial']==inv.get('candidate_soa_serial')
    result['ok']=exact
    result['status']='in_sync' if exact else ('public_drift' if rec.get('mismatch_count') else 'serial_or_inventory_drift')
    return result

def main():
    zones=[check(p) for p in inventory_paths() if p.exists()]
    payload={'contract':'edge1.dns-zone-inventory.v1','generated_at':now(),'provider':'Dyn Standard DNS','publication_method':'authenticated TSIG/API synchronization','zones':zones,'all_in_sync':bool(zones) and all(z.get('ok') for z in zones)}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUTPUT.with_name('.'+OUTPUT.name+'.tmp'); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); tmp.replace(OUTPUT)
    print(json.dumps({'ok':payload['all_in_sync'],'zones':[(z['zone'],z['status']) for z in zones]},sort_keys=True))
    raise SystemExit(0 if payload['all_in_sync'] else 1)

if __name__=='__main__': main()
