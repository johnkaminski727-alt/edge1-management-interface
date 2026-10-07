#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
IDENT=Path('/etc/wwcx/outbound-mail/identities.json'); GATE=Path('/var/www/edge1-status/email-gateway/status.json'); DNS=Path('/var/www/edge1-status/dns-management.json'); READY=Path('/var/lib/wwcx-mail-room-reports/readiness.json'); STATUS=Path('/var/www/edge1-status/mail-domain-health/status.json'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
def load(p):
    try:return json.loads(p.read_text())
    except Exception:return {}
def age_minutes(v):
    try:return (datetime.now(timezone.utc)-datetime.fromisoformat(str(v).replace('Z','+00:00'))).total_seconds()/60
    except Exception:return None
def build():
    ids=load(IDENT); gate=load(GATE); dns=load(DNS); ready=load(READY); configured=sorted((ids.get('domains') or {}).keys()); observed={x.get('domain'):x for x in gate.get('domains',[]) if x.get('domain')}; warnings=[]; followups=[]; rows=[]
    freshness=age_minutes(gate.get('generated_at'));
    if freshness is None or freshness>15:warnings.append('email_gateway_status_stale')
    for domain in configured:
        g=observed.get(domain,{})
        checks=g.get('checks') if isinstance(g.get('checks'),dict) else {}
        failed=[k for k,v in checks.items() if v is False]
        rows.append({'domain':domain,'commissioned':bool(g.get('commissioned')),'sending_enabled':bool(g.get('sending_enabled')),'migration_state':g.get('migration_state'),'failed_checks':failed,'mx_answer_count':g.get('mx_answer_count')})
        if failed:warnings.append(domain+':checks_failed')
    svc=gate.get('services') or {}; bad_services=[k for k,v in svc.items() if isinstance(v,dict) and str(v.get('active')).lower() not in {'active','true'}]
    if bad_services:warnings.append('mail_services_inactive')
    auth=dns.get('authoritative_dns') or {}; resolver=dns.get('resolver') or {}
    if resolver.get('adguard_active') is False or resolver.get('unbound_active') is False:warnings.append('resolver_component_inactive')
    auth_state=auth.get('state')
    if auth.get('enabled') and auth_state not in {'active','healthy','accepted_live'}:
        if auth_state=='local_active_pending_secondary': followups.append('authoritative_dns_secondary_pending')
        else: warnings.append('authoritative_dns_attention')
    backlog=gate.get('backlog') or {}; pending=int(backlog.get('pending_or_unchecked') or 0)
    if pending>100:warnings.append('mail_backlog_high')
    return {'contract':'wwcx.mail-domain-health.v1','generated_at':utcnow(),'state':'attention' if warnings else 'healthy','configured_domains':rows,'service_issues':bad_services,'gateway_status_age_minutes':round(freshness,1) if freshness is not None else None,'backlog_pending_or_unchecked':pending,'dns':{'adguard_active':resolver.get('adguard_active'),'unbound_active':resolver.get('unbound_active'),'authoritative_state':auth.get('state'),'wireguard_split_dns_preserved':auth.get('wireguard_split_dns_preserved')},'warnings':sorted(set(warnings)),'followups':sorted(set(followups)),'secrets_exposed':False,'mutation_performed':False}
def md(d):
    lines=['# Mail & Domain Health','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Pending/unchecked mail: **{d['backlog_pending_or_unchecked']}**",'', '## Domains','']+[f"- **{x['domain']}** — commissioned={x['commissioned']} sending={x['sending_enabled']} migration={x['migration_state']} failed_checks={x['failed_checks']}" for x in d['configured_domains']]
    lines += ['','## Warnings','']+([f'- {x}' for x in d['warnings']] or ['- None.'])+['','This monitor is read-only and exposes no mail credentials or message content.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/mail-domain-health/current.md','Mail & Domain Health',md(d)); print(json.dumps({'state':d['state'],'domains':len(d['configured_domains']),'warnings':len(d['warnings'])},sort_keys=True))
if __name__=='__main__':main()
