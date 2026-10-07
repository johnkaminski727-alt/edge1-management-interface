#!/usr/bin/env python3
"""Publish a sanitized DNS/resolver/security management snapshot."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import yaml
DEFAULT_ADGUARD=Path('/opt/AdGuardHome/AdGuardHome.yaml')
DEFAULT_IDENTITY=Path('/var/www/edge1-status/wireguard-identity.json')
DEFAULT_TELEMETRY=Path('/var/www/edge1-status/wireguard-dns-security.json')
DEFAULT_CROWDSEC=Path('/var/www/edge1-status/crowdsec-status.json')
DEFAULT_LOCAL=Path('/var/www/edge1-status/wireguard-local-dns.json')
DEFAULT_OUTPUT=Path('/var/www/edge1-status/dns-management.json')
DEFAULT_AUTH_POLICY=Path('/opt/edge1-management-interface/config/dns/hidden-primary-policy.json')
DEFAULT_AUTH_INVENTORY=Path('/var/lib/edge1-authoritative-dns/ww.cx-inventory.json')
DEFAULT_AUTH_ZONE=Path('/var/lib/edge1-authoritative-dns/ww.cx.zone')
DEFAULT_AUTH_LOCAL_ACTIVE=Path('/var/lib/edge1-authoritative-dns/LOCAL_ACTIVE')

def load_json(path):
 try:return json.loads(path.read_text())
 except Exception:return {}
def build(adguard_path,identity_path,telemetry_path,crowdsec_path,local_path,auth_policy=DEFAULT_AUTH_POLICY,auth_inventory=DEFAULT_AUTH_INVENTORY,auth_zone=DEFAULT_AUTH_ZONE,auth_local_active=DEFAULT_AUTH_LOCAL_ACTIVE):
 a=yaml.safe_load(adguard_path.read_text()) or {}; dns=a.get('dns') or {}; filtering=a.get('filtering') or {}
 identity=load_json(identity_path); telem=load_json(telemetry_path); crowd=load_json(crowdsec_path); local=load_json(local_path)
 filters=[]
 for item in a.get('filters') or []:
  if not isinstance(item,dict):continue
  filters.append({'name':str(item.get('name') or 'Unnamed')[:120],'enabled':bool(item.get('enabled')),'id':item.get('id')})
 rewrites=[]
 for item in filtering.get('rewrites') or []:
  if not isinstance(item,dict) or not item.get('enabled'):continue
  rewrites.append({'domain':str(item.get('domain') or '')[:253],'answer':str(item.get('answer') or '')[:253]})
 services=crowd.get('services') if isinstance(crowd.get('services'),dict) else {}
 rows=[]
 obs={x.get('address'):x for x in telem.get('devices') or []}
 for d in identity.get('devices') or []:
  address=((d.get('assigned_addresses') or [''])[0]).split('/')[0]; t=obs.get(address,{})
  rows.append({'name':d.get('name'),'address':address,'owner_display_name':d.get('owner_display_name'),'registration_status':d.get('registration_status'),'queries_24h':(t.get('dns') or {}).get('queries_24h',0),'blocked_24h':(t.get('dns') or {}).get('blocked_24h',0),'edge1_dns_observed':((t.get('dns') or {}).get('queries_24h',0)>0)})
 policy=load_json(auth_policy); inventory=load_json(auth_inventory)
 inventory_complete=inventory.get('complete_zone_inventory') is True
 zone_present=auth_zone.is_file()
 zone_hash=(hashlib.sha256(auth_zone.read_bytes()).hexdigest() if zone_present else None)
 candidate_valid=bool(inventory_complete and zone_present and inventory.get('zone_file_sha256')==zone_hash and inventory.get('candidate_soa_serial'))
 local_active=auth_local_active.is_file()
 if candidate_valid: hp_state='operational'
 else: hp_state='staged_blocked'
 blockers=[]
 if not inventory_complete: blockers.append('complete_zone_inventory_missing')
 if not zone_present: blockers.append('candidate_zone_file_missing')
 if inventory_complete and zone_present and not candidate_valid: blockers.append('candidate_validation_mismatch')
 return {'schema_version':1,'contract':'wwcx.dns-management.v1','resolver':{'adguard_active':bool((services.get('AdGuardHome') or {}).get('active')),'unbound_active':bool((services.get('unbound') or {}).get('active')),'listen_address':'10.77.0.1','upstream_role':'Unbound recursive resolver','dnssec_enabled':bool(dns.get('enable_dnssec')),'cache_size':dns.get('cache_size'),'private_ptr_upstream_configured':bool(dns.get('local_ptr_upstreams')),'filtering_enabled':bool(filtering.get('filtering_enabled')),'protection_enabled':bool(filtering.get('protection_enabled'))},'filters':filters,'rewrites':rewrites,'wireguard':{'split_dns_preserved':bool(identity.get('split_dns_preserved')),'exclusive_dns_target':'10.77.0.1','devices':rows,'all_observed_on_edge1_dns':bool(rows) and all(r['edge1_dns_observed'] for r in rows)},'private_dns':{'zone':local.get('zone','wg.internal.ww.cx.'),'record_count':local.get('record_count',0)+sum(1 for x in rewrites if str(x.get('answer','')).startswith('10.77.')),'wireguard_record_count':local.get('record_count',0),'split_dns_rewrite_count':sum(1 for x in rewrites if str(x.get('answer','')).startswith('10.77.')),'generated_at':local.get('generated_at')},'security':{'crowdsec_active':bool((services.get('crowdsec') or {}).get('active')),'crowdsec_bouncer_active':bool((services.get('crowdsec-firewall-bouncer') or {}).get('active')),'spamhaus_policy_enabled_count':sum(1 for d in identity.get('devices') or [] if (d.get('security') or {}).get('spamhaus_enabled'))},'authoritative_dns':{'mode':'source-of-truth-publish','state':hp_state,'publicly_exposed':False,'enabled':candidate_valid,'local_primary_active':False,'secondary_verified':None,'recursive_service_separate':bool(policy.get('recursive_service_separate',True)),'wireguard_split_dns_preserved':bool(policy.get('wireguard_split_dns_preserved',True)),'public_authoritative_provider':policy.get('public_authoritative_provider','Dyn Standard DNS'),'publication_method':policy.get('publication_method','authenticated TSIG/API synchronization'),'secondary_dns_supported_by_provider':bool(policy.get('secondary_dns_supported_by_provider',False)),'secondary_dns_status':policy.get('secondary_dns_status','not_applicable'),'public_dns_listener_required':bool(policy.get('public_dns_listener_required',False)),'complete_zone_inventory':inventory_complete,'candidate_zone_present':zone_present,'candidate_validated':candidate_valid,'record_count':inventory.get('record_count',0) if inventory_complete else 0,'exported_soa_serial':inventory.get('exported_soa_serial'),'observed_public_soa_serial':inventory.get('observed_public_soa_serial'),'candidate_soa_serial':inventory.get('candidate_soa_serial'),'activation_blockers':blockers,'public_delegation_change_authorized':bool(policy.get('public_delegation_change_authorized')),'mx_cutover_authorized':bool(policy.get('mx_cutover_authorized'))}}
def write_atomic(path,payload):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name('.'+path.name+'.tmp'); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); tmp.chmod(0o644); tmp.replace(path); path.chmod(0o644)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--adguard',type=Path,default=DEFAULT_ADGUARD); ap.add_argument('--identity',type=Path,default=DEFAULT_IDENTITY); ap.add_argument('--telemetry',type=Path,default=DEFAULT_TELEMETRY); ap.add_argument('--crowdsec',type=Path,default=DEFAULT_CROWDSEC); ap.add_argument('--local-status',type=Path,default=DEFAULT_LOCAL); ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); a=ap.parse_args(); p=build(a.adguard,a.identity,a.telemetry,a.crowdsec,a.local_status); write_atomic(a.output,p); print(json.dumps({'ok':True,'output':str(a.output),'device_count':len(p['wireguard']['devices']),'filter_count':len(p['filters'])},sort_keys=True))
if __name__=='__main__':main()
