#!/usr/bin/env python3
from __future__ import annotations
import datetime,json,pathlib,subprocess

READINESS=pathlib.Path('/var/lib/wwcx-mail-room-reports/readiness.json')
CANARY_CONFIG=pathlib.Path('/opt/edge1-management-interface/config/messaging/wwcx-mail-canary.json')
DST=pathlib.Path('/var/www/edge1-status/email-gateway/status.json')
CANARY_DST=pathlib.Path('/var/www/edge1-status/email-gateway/wwcx-canary-status.json')
EXTERNAL_SMTP=pathlib.Path('/var/lib/wwcx-mail-gateway/external-smtp-acceptance.json')
SECURITY_ACCEPTANCE=pathlib.Path('/var/lib/wwcx-mail-gateway/inbound-security-acceptance.json')

def active(unit):
    p=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True)
    return p.stdout.strip() or 'unknown'
def enabled(unit):
    p=subprocess.run(['systemctl','is-enabled',unit],capture_output=True,text=True)
    return p.stdout.strip() or 'unknown'
def dig(name,typ):
    p=subprocess.run(['dig','+short',name,typ,'@1.1.1.1'],capture_output=True,text=True,timeout=8)
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]
def write_json(path,payload,mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.tmp')
    tmp.write_text(json.dumps(payload,indent=2)+'\n')
    tmp.chmod(mode);tmp.replace(path)

def openpgp_status():
    tool='/opt/edge1-management-interface/tools/messaging/openpgp_commissioning_status.py'
    try:
        p=subprocess.run(['/usr/bin/python3',tool],capture_output=True,text=True,timeout=5,check=False)
        if p.returncode!=0: return {'available':False,'error':'status command failed'}
        data=json.loads(p.stdout)
        service=data.get('service') or {}
        key=data.get('contacts_key') or {}
        return {
          'available':True,
          'service_active':active('wwcx-openpgp-crypto'),
          'public_key_count':service.get('public_key_count',0),
          'secret_key_count':service.get('secret_key_count',0),
          'sign_enabled':bool(service.get('sign_enabled',False)),
          'encrypt_enabled':bool(service.get('encrypt_enabled',False)),
          'decrypt_enabled':bool(service.get('decrypt_enabled',False)),
          'contacts_key_registered':bool(key),
          'contacts_key_verified':key.get('verification_status')=='verified',
          'contacts_policy':data.get('contacts_policy'),
          'public_key_published':bool(data.get('public_key_published',False)),
          'ready_for_sign_only':bool(data.get('ready_for_sign_only',False)),
          'private_key_export_supported':False,
        }
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError):
        return {'available':False,'error':'status unavailable'}

def canary_status():
    if not CANARY_CONFIG.is_file(): return None
    cfg=json.loads(CANARY_CONFIG.read_text())
    if cfg.get('contract')!='wwcx.mail-canary.v1': return None
    gates=dict(cfg.get('cutover_gates') or {})
    a=dig('mail.ww.cx','A');mx=dig('ww.cx','MX');spf=dig('ww.cx','TXT')
    dmarc=dig('_dmarc.ww.cx','TXT');dkim=dig('edge1-202610._domainkey.ww.cx','TXT')
    ptr=dig('191.248.126.89.in-addr.arpa','PTR')
    gates['mail_a_published']='89.126.248.191' in a
    gates['dkim_published']=bool(dkim)
    production_mx = any(x.strip() == '10 mail.ww.cx.' for x in mx)
    final_spf = any('v=spf1' in x and 'ip4:89.126.248.191' in x and 'spf.privateemail.com' not in x for x in spf)
    overlap_spf = any('89.126.248.191' in x and 'spf.privateemail.com' in x for x in spf)
    gates['spf_overlap_published'] = final_spf if production_mx else overlap_spf
    gates['dmarc_monitoring_published']=any('v=DMARC1' in x and 'p=none' in x for x in dmarc)
    gates['ptr_forward_confirmed']=any(x.rstrip('.')=='mail.ww.cx' for x in ptr)
    gates['tls_certificate_ready']=pathlib.Path('/etc/letsencrypt/live/mail.ww.cx/fullchain.pem').is_file()
    external=json.loads(EXTERNAL_SMTP.read_text()) if EXTERNAL_SMTP.is_file() else {}
    security=json.loads(SECURITY_ACCEPTANCE.read_text()) if SECURITY_ACCEPTANCE.is_file() else {}
    gates['external_smtp_reachable']=external.get('result')=='pass' and external.get('nodes_connected',0)>=3
    gates['inbound_security_acceptance']=security.get('result')=='pass'
    foundational=('mail_a_published','tls_certificate_ready','dkim_published','spf_overlap_published','dmarc_monitoring_published','inbound_loopback_acceptance','external_smtp_reachable','inbound_security_acceptance')
    state='pre_cutover_staging'
    pilot_ok = False
    pilot_root = pathlib.Path('/var/lib/wwcx-mail-gateway')
    for item in sorted(pilot_root.glob('outbound-pilot-*/execution.json'), reverse=True):
        try:
            data = json.loads(item.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        submission = data.get('submission') or {}
        if data.get('contract') == 'wwcx.direct-mta-one-message-pilot.v1' and submission.get('accepted') is True and submission.get('smtp_code') == 250 and data.get('rollback_succeeded') is True:
            pilot_ok = True
            break
    gates['outbound_one_message_pilot'] = pilot_ok
    rollback_file = pathlib.Path('/var/lib/wwcx-mail-gateway/wwcx-external-dns-rollback-rehearsal.json')
    try:
        rollback = json.loads(rollback_file.read_text()) if rollback_file.is_file() else {}
    except (OSError, json.JSONDecodeError):
        rollback = {}
    gates['rollback_rehearsal'] = rollback.get('result') == 'pass' and rollback.get('rollback_restored_baseline') is True and rollback.get('cleanup_absent_on_all_authoritative_nameservers') is True and rollback.get('production_records_touched') is False
    activation = dict(cfg.get('activation') or {})
    activation['production_mx_changed'] = production_mx
    activation['outbound_delivery_enabled'] = bool(gates['outbound_one_message_pilot'])
    if all(gates.get(k) is True for k in foundational):
        state='waiting_ptr_and_final_gates'
    if all(gates.get(k) is True for k in (*foundational,'ptr_forward_confirmed','outbound_one_message_pilot','rollback_rehearsal')):
        state='pre_cutover_ready'
    if production_mx:
        state='smoke_test_live'
    return {
      'contract':'wwcx.mail-canary-status.v1','updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'domain':'ww.cx','state':state,'smoke_test_hours':'24-48','activation':activation,
      'cutover_gates':gates,'public_observed':{'mail_a':a,'mx':mx,'ptr':ptr},
      'remaining_blockers':[k for k,v in gates.items() if v is not True],
      'other_domains_untouched':True,'acceptance_evidence':{'external_smtp':external,'inbound_security':security},
    }

def main():
    raw=json.loads(READINESS.read_text()) if READINESS.exists() else {}
    domains=[]
    for x in raw.get('domains',[]):
        domains.append({'domain':x.get('domain'),'migration_state':x.get('migration_state'),'commissioned':bool(x.get('commissioned',False)),'sending_enabled':bool(x.get('sending_enabled',False)),'registered_senders':x.get('registered_senders'),'checks':x.get('checks',{}),'mx_answer_count':(x.get('dns_baseline') or {}).get('mx_answer_count')})
    units=['postfix','rspamd','wwcx-openpgp-crypto','wwcx-mail-clamd','wwcx-outbound-mail-gateway','wwcx-mail-room','wwcx-mail-security-scan.timer','wwcx-mail-readiness.timer','wwcx-mail-update-definitions.timer','wwcx-mail-update-packages.timer']
    canary=canary_status()
    openpgp=openpgp_status()
    out={'contract':'wwcx.edge1-email-gateway-status.v1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_generated_at':raw.get('generated_at'),'services':{u:{'active':active(u),'enabled':enabled(u)} for u in units},'domains':domains,'backlog':raw.get('backlog',{}),'updates':raw.get('updates',{}),'recovery':raw.get('recovery',{}),'access_policy':raw.get('access_policy',{}),'dns_changes_applied':raw.get('dns_changes_applied'),'send_enabled':raw.get('send_enabled'),'canary':canary,'openpgp':openpgp,'content_included':False}
    write_json(DST,out)
    if canary: write_json(CANARY_DST,canary)
    print(json.dumps({'exported':True,'domains':len(domains),'send_enabled':out['send_enabled'],'canary_state':canary.get('state') if canary else None}))
if __name__=='__main__': main()
