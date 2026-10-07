#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path('/var/www/edge1-status/dns-zone-inventory.json')
RECONCILE = Path('/opt/edge1-management-interface/tools/dns/reconcile_hidden_primary_candidate.py')
MANAGED = Path('/opt/edge1-management-interface/config/dns/managed-zones.json')

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def load_json(path: Path):
    try: return json.loads(path.read_text())
    except Exception: return {}

def dig_short(name: str, typ: str, ns: str | None = None):
    cmd=['/usr/bin/dig','+short','+time=4','+tries=1']
    if ns: cmd.append('@'+ns)
    cmd += [name,typ]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=7)
    return [x.strip() for x in p.stdout.splitlines() if x.strip()] if p.returncode==0 else []

def soa_serial(zone: str, ns: str):
    vals=dig_short(zone,'SOA',ns)
    if not vals: return None
    parts=vals[0].split()
    return int(parts[2]) if len(parts)>=3 and parts[2].isdigit() else None

def check_edge1_canonical(cfg: dict):
    zone=str(cfg.get('zone') or '').rstrip('.')
    inv_path=Path(str(cfg.get('inventory_file') or ''))
    inv=load_json(inv_path)
    zone_file=Path(str(cfg.get('zone_file') or inv.get('candidate_zone_file') or ''))
    nss=[str(x).rstrip('.') for x in cfg.get('authoritative_nameservers',[]) if x]
    result={
      'zone':zone,'mode':'edge1_canonical','provider':cfg.get('provider','Dyn Standard DNS'),
      'management_path':cfg.get('management_path','Edge1 validated publishing'),
      'inventory_file':str(inv_path),'zone_file':str(zone_file),'record_count':inv.get('record_count',0),
      'candidate_soa_serial':inv.get('candidate_soa_serial'),'mx_cutover_authorized':bool(cfg.get('mx_cutover_authorized',False)),
      'authoritative_nameservers':nss
    }
    if not zone or not inv_path.is_file() or not zone_file.is_file() or not nss:
        result.update({'status':'configuration_problem','ok':False,'mismatch_count':None,'public_serials':{}}); return result
    digest=hashlib.sha256(zone_file.read_bytes()).hexdigest()
    result['candidate_hash_matches_inventory']=(digest==inv.get('zone_file_sha256'))
    result['public_serials']={ns:soa_serial(zone,ns) for ns in nss}
    cmd=['/usr/bin/python3',str(RECONCILE),'--zone-file',str(zone_file),'--zone',zone]
    for ns in nss: cmd += ['--nameserver',ns]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=60)
    try: rec=json.loads(p.stdout)
    except Exception: rec={'ok':False,'mismatch_count':None,'mismatches':[{'error':(p.stderr or p.stdout or 'reconcile failed')[:500]}]}
    result['mismatch_count']=rec.get('mismatch_count'); result['mismatches']=rec.get('mismatches',[])
    serials=list(result['public_serials'].values())
    serial_agree=bool(serials) and all(v is not None for v in serials) and len(set(serials))==1
    result['public_serial_agreement']=serial_agree
    result['public_soa_serial']=serials[0] if serial_agree else None
    exact=bool(rec.get('ok')) and result['candidate_hash_matches_inventory'] and serial_agree and result['public_soa_serial']==inv.get('candidate_soa_serial')
    result['ok']=exact
    result['status']='matches_edge1' if exact else ('public_records_differ' if rec.get('mismatch_count') else 'serial_or_inventory_difference')
    return result

def check_business159(cfg: dict):
    zone=str(cfg.get('zone') or '').rstrip('.')
    nss=[str(x).rstrip('.') for x in cfg.get('authoritative_nameservers',[]) if x]
    expected_ip=str(cfg.get('expected_web_address') or '')
    result={
      'zone':zone,'mode':'business159_observed','provider':cfg.get('provider','Namecheap Hosting DNS'),
      'management_path':cfg.get('management_path','Business159 / cPanel DNS'),'record_count':None,
      'candidate_soa_serial':None,'mx_cutover_authorized':bool(cfg.get('mx_cutover_authorized',False)),
      'authoritative_nameservers':nss
    }
    serials={ns:soa_serial(zone,ns) for ns in nss}
    result['public_serials']=serials
    vals=list(serials.values())
    serial_agree=bool(vals) and all(v is not None for v in vals) and len(set(vals))==1
    result['public_serial_agreement']=serial_agree
    result['public_soa_serial']=vals[0] if serial_agree else None
    published_ns=sorted(x.rstrip('.').lower() for x in dig_short(zone,'NS'))
    expected_ns=sorted(x.lower() for x in nss)
    result['nameservers_match']=published_ns==expected_ns
    addresses=sorted(x for x in dig_short(zone,'A'))
    result['public_addresses']=addresses
    result['web_address_matches']=bool(expected_ip) and expected_ip in addresses
    ok=serial_agree and result['nameservers_match'] and (result['web_address_matches'] if expected_ip else True)
    result['ok']=ok
    result['status']='public_dns_healthy' if ok else 'public_dns_attention'
    result['mismatch_count']=0 if ok else None
    result['mismatches']=[]
    return result

def main():
    cfg=load_json(MANAGED)
    zones=[]
    for z in cfg.get('zones',[]):
        mode=z.get('mode')
        zones.append(check_edge1_canonical(z) if mode=='edge1_canonical' else check_business159(z))
    all_ok=bool(zones) and all(z.get('ok') for z in zones)
    payload={
      'contract':'edge1.dns-zone-inventory.v2','generated_at':now(),
      'zones':zones,'all_operational':all_ok,'all_in_sync':all_ok,
      'providers':sorted({str(z.get('provider')) for z in zones if z.get('provider')})
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUTPUT.with_name('.'+OUTPUT.name+'.tmp')
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    tmp.chmod(0o644); tmp.replace(OUTPUT); OUTPUT.chmod(0o644)
    print(json.dumps({'ok':all_ok,'zones':[(z['zone'],z['status']) for z in zones]},sort_keys=True))
    raise SystemExit(0 if all_ok else 1)

if __name__=='__main__': main()
