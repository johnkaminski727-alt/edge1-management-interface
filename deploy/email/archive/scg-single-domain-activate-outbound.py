#!/usr/bin/env python3
"""Deploy the approved SCG-only local MTA route; preserve rollback files."""
import json,os,shutil,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3]
def run(*args): subprocess.run(args,check=True)
def main():
    if os.geteuid()!=0 or sys.argv[1:]!=["--apply"]: raise SystemExit("root and --apply required")
    sys.path.insert(0,str(ROOT/"server"))
    import mail_local_mta,mail_final_scan
    mail_final_scan.require_clean(b"Subject: SCG scanner preflight\r\n\r\nClean commissioning message.\r\n",mail_local_mta.scan)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup=Path('/var/backups/scg-outbound-'+stamp);backup.mkdir(mode=0o700)
    targets=["/etc/postfix/main.cf","/etc/postfix/master.cf","/etc/wwcx/outbound-mail/gateway.json","/etc/wwcx/outbound-mail/policy.json","/etc/wwcx/outbound-mail/identities.json"]
    manifest={}
    for target in targets:
        saved=backup/target.lstrip('/').replace('/','_');shutil.copy2(target,saved);manifest[target]=str(saved)
    (backup/'rollback.json').write_text(json.dumps(manifest,indent=2))
    release=Path('/opt/wwcx-email/releases/scg-local-mta-'+stamp)
    shutil.copytree('/opt/wwcx-email/releases/scg-catchall-gateway-20261006',release)
    for name in ['outbound_mail_gateway.py','mail_secure_submission.py','mail_identity_registry.py','identity_aware_outbound_gateway.py','outbound_mail_gateway_suppressed_server.py','outbound_mail_gateway_runtime_server.py','mail_local_mta.py']:
        shutil.copy2(ROOT/'server'/name,release/'server'/name);os.chmod(release/'server'/name,0o644)
    gateway=Path('/etc/wwcx/outbound-mail/gateway.json');g=json.loads(gateway.read_text())
    g.update(enabled=True,deployment_authorized=True,external_delivery_authorized=True)
    g['provider']['selected']='edge1_local_mta'
    g['provider']['profiles']['edge1_local_mta']={'type':'local_mta','enabled':True,'allowed_from_domains':['spiritcreekgardens.com']}
    g['admin']['send_endpoint_enabled']=True
    g['admin']['max_recipient_count']=25
    policy=Path('/etc/wwcx/outbound-mail/policy.json');p=json.loads(policy.read_text())
    p.update(enabled=True,deployment_authorized=True,smtp_cutover_authorized=True)
    p['delivery'].update(provider='smtp_submission',allow_external_submission=True,allow_live_delivery=True,allowed_from_domains=['spiritcreekgardens.com'])
    p['organization'].update(legal_name='Spirit Creek Gardens Inc.',operating_name='Spirit Creek Gardens',website='https://spiritcreekgardens.com',privacy_url='https://spiritcreekgardens.com/privacy',contact_email='contact@spiritcreekgardens.com',mailing_address='PO Box 333, Invermay, SK S0A 1M0, Canada')
    identities=Path('/etc/wwcx/outbound-mail/identities.json');i=json.loads(identities.read_text())
    i['outbound_activation_authorized']=True
    i['sender_selection']['live_sender_allowlist']=['contact@spiritcreekgardens.com']
    i['sender_profiles']['spirit-creek-gardens-contact']['outbound_enabled']=True
    import outbound_mail_gateway as core,outbound_mail_policy as pol,mail_identity_registry as ids
    core.validate_gateway_config(g);pol.validate_policy(p);ids.validate_registry(i)
    for path,value in [(gateway,g),(policy,p),(identities,i)]:path.write_text(json.dumps(value,indent=2)+'\n')
    drop=Path('/etc/systemd/system/wwcx-outbound-mail-gateway.service.d/80-scg-local-mta.conf')
    drop.write_text(f'[Service]\nWorkingDirectory={release}\nExecStart=\nExecStart=/usr/bin/python3 {release}/server/outbound_mail_gateway_runtime_server.py --config /etc/wwcx/outbound-mail/gateway.json --identities /etc/wwcx/outbound-mail/identities.json --host 127.0.0.1 --port 8104\n')
    os.chmod(drop,0o644)
    # Sender routing keeps all other domains at the error transport baseline.
    route=Path('/etc/postfix/scg-outbound-transports');route.write_text('/^[^@[:space:]]+@spiritcreekgardens\\.com$/ smtp:\n');os.chmod(route,0o644)
    senders=Path('/etc/postfix/scg-submission-senders');senders.write_text('/^[^@[:space:]]+@spiritcreekgardens\\.com$/ OK\n/.*/ REJECT SCG sender required\n');os.chmod(senders,0o644)
    master=Path('/etc/postfix/master.cf')
    master.write_text(master.read_text()+"\n# SCG authenticated gateway loopback submission\n127.0.0.1:10027 inet n - y - - smtpd\n  -o syslog_name=postfix/scg-submission\n  -o smtpd_milters=inet:127.0.0.1:11332\n  -o milter_default_action=tempfail\n  -o smtpd_client_restrictions=permit_mynetworks,reject\n  -o smtpd_sender_restrictions=check_sender_access,regexp:/etc/postfix/scg-submission-senders,reject\n  -o smtpd_relay_restrictions=permit_mynetworks,reject\n  -o smtpd_recipient_restrictions=permit_mynetworks,reject\n")
    run('postconf','-e','sender_dependent_default_transport_maps=regexp:/etc/postfix/scg-outbound-transports')
    run('postconf','-e','smtp_tls_security_level=may')
    db=Path('/var/lib/wwcx-outbound-mail/delivery-state.sqlite3')
    if not db.exists():run('sudo','-u','wwcx-mail-gateway','python3','-B',str(ROOT/'tools/messaging/initialize_outbound_mail_delivery_state.py'),'--database',str(db))
    run('postfix','check');run('postfix','reload');run('systemctl','daemon-reload');run('systemctl','restart','wwcx-outbound-mail-gateway')
    print(json.dumps({'backup':str(backup),'release':str(release),'domain':'spiritcreekgardens.com'}))
if __name__=='__main__':main()
