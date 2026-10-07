#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
CROWD=Path('/var/www/edge1-status/crowdsec-status.json')
NFT=Path('/var/lib/bigbird-networking/nftables/live-state.json')
CANARY=Path('/var/www/edge1-status/email-gateway/wwcx-canary-status.json')
API_HEALTH=Path('/var/www/edge1-status/api-surface-health/status.json')
CORRELATION=Path('/var/www/edge1-status/security-correlation.json')
SPAMHAUS=Path('/var/lib/edge1-spamhaus/status')
STATUS=Path('/var/www/edge1-status/security-baseline/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
REQUIRED_OBSERVED_SERVICES=('ufw','crowdsec','crowdsec-firewall-bouncer','AdGuardHome','unbound')
REQUIRED_SYSTEMD=(
 'wwcx-network-sensor-suricata.service','wwcx-mail-room.service','wwcx-mail-security-scan.timer',
 'edge1-spamhaus-refresh.timer','wwcx-nftables-live-state.timer','edge1-security-correlation-observation.timer',
)

def load(path):
    try:return json.loads(path.read_text())
    except Exception:return {}
def parse_time(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None
def age_minutes(value,now):
    stamp=parse_time(value)
    return None if stamp is None else max(0,(now-stamp).total_seconds()/60)
def unit_state(unit):
    def run(*args): return subprocess.run(args,text=True,capture_output=True,check=False).stdout.strip()
    return {'active':run('systemctl','is-active',unit) or 'unknown','enabled':run('systemctl','is-enabled',unit) or 'unknown','result':run('systemctl','show',unit,'-p','Result','--value') or None,'exit':run('systemctl','show',unit,'-p','ExecMainStatus','--value') or None}
def parse_spamhaus(path):
    out={}
    try:
        for line in path.read_text().splitlines():
            if '=' in line:
                k,v=line.split('=',1); out[k.strip()]=v.strip()
    except OSError: pass
    return out
def add(findings,kind,severity,detail): findings.append({'kind':kind,'severity':severity,'detail':detail,'action_level':'REVIEW-REQUIRED'})
def evaluate(crowd,nft,canary,api_health,correlation,spamhaus,units,now=None):
    now=now or datetime.now(timezone.utc); findings=[]; checks=[]
    def check(name,ok,detail,severity='high'):
        checks.append({'name':name,'ok':bool(ok),'detail':detail})
        if not ok:add(findings,name,severity,detail)
    crowd_age=age_minutes(crowd.get('generated_at'),now)
    check('crowdsec_snapshot_fresh',crowd_age is not None and crowd_age<=10,f'CrowdSec snapshot age_minutes={None if crowd_age is None else round(crowd_age,1)}','medium')
    check('crowdsec_snapshot_read_only',crowd.get('read_only') is True and crowd.get('traffic_controls_changed') is False,'CrowdSec observer must remain read-only.','high')
    observed=crowd.get('services') if isinstance(crowd.get('services'),dict) else {}
    for name in REQUIRED_OBSERVED_SERVICES:
        row=observed.get(name) if isinstance(observed.get(name),dict) else {}
        check('service_'+name, row.get('active') is True and row.get('enabled') is True and row.get('observed') is True, f'{name}: active={row.get("active")} enabled={row.get("enabled")} observed={row.get("observed")}')
    for unit in REQUIRED_SYSTEMD:
        row=units.get(unit,{})
        active_ok=row.get('active')=='active'
        enabled_ok=row.get('enabled') in {'enabled','static'}
        check('unit_'+unit,active_ok and enabled_ok and row.get('result') in {None,'success'},f'{unit}: active={row.get("active")} enabled={row.get("enabled")} result={row.get("result")} exit={row.get("exit")}')
    nft_age=age_minutes(nft.get('generated_at'),now); agg=nft.get('aggregates') if isinstance(nft.get('aggregates'),dict) else {}; objects=agg.get('objects') if isinstance(agg.get('objects'),dict) else {}; rules=agg.get('rules') if isinstance(agg.get('rules'),dict) else {}; verdicts=rules.get('verdicts') if isinstance(rules.get('verdicts'),dict) else {}; elems=agg.get('elements') if isinstance(agg.get('elements'),dict) else {}; obs=nft.get('observation') if isinstance(nft.get('observation'),dict) else {}
    check('nftables_snapshot_fresh',nft_age is not None and nft_age<=5,f'nftables snapshot age_minutes={None if nft_age is None else round(nft_age,1)}','medium')
    check('nftables_ruleset_observed',obs.get('observed') is True and not nft.get('errors'),f'observed={obs.get("observed")} errors={nft.get("errors")}')
    check('nftables_nonempty',int(objects.get('rule') or 0)>0 and int(objects.get('set') or 0)>0 and int(verdicts.get('drop') or 0)>0 and int(elems.get('set_count') or 0)>0,f'rules={objects.get("rule")} sets={objects.get("set")} drop_verdicts={verdicts.get("drop")} set_elements={elems.get("set_count")}')
    spam4=int(spamhaus.get('drop4') or 0); spam6=int(spamhaus.get('drop6') or 0); spam_stamp=spamhaus.get('last_success_utc'); spam_dt=None
    if spam_stamp:
        try: spam_dt=datetime.strptime(spam_stamp,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        except ValueError: pass
    spam_age=None if spam_dt is None else (now-spam_dt).total_seconds()/3600
    check('spamhaus_feed_fresh',spam4>0 and spam6>0 and spam_age is not None and spam_age<=36,f'drop4={spam4} drop6={spam6} age_hours={None if spam_age is None else round(spam_age,1)}')
    blockers=canary.get('remaining_blockers') if isinstance(canary.get('remaining_blockers'),list) else None; gates=canary.get('cutover_gates') if isinstance(canary.get('cutover_gates'),dict) else {}
    check('mail_security_gates',blockers==[] and gates.get('inbound_security_acceptance') is True and canary.get('other_domains_untouched') is True,f'blockers={blockers} inbound_security={gates.get("inbound_security_acceptance")} other_domains_untouched={canary.get("other_domains_untouched")}')
    check('api_private_surface',api_health.get('state')=='healthy' and int((api_health.get('summary') or {}).get('high') or 0)==0,f'api_surface_state={api_health.get("state")} high={((api_health.get("summary") or {}).get("high"))}')
    corr_age=age_minutes(correlation.get('generated_at'),now)
    check('security_correlation_fresh',corr_age is not None and corr_age<=10,f'correlation age_minutes={None if corr_age is None else round(corr_age,1)}','medium')
    state='attention' if any(x['severity']=='high' for x in findings) else 'warning' if findings else 'healthy'
    return {'contract':'wwcx.security-baseline.v1','generated_at':now.isoformat(),'state':state,'summary':{'checks':len(checks),'passed':sum(x['ok'] for x in checks),'findings':len(findings),'high':sum(x['severity']=='high' for x in findings),'medium':sum(x['severity']=='medium' for x in findings),'spamhaus_ipv4':spam4,'spamhaus_ipv6':spam6,'nft_rules':int(objects.get('rule') or 0),'nft_drop_verdicts':int(verdicts.get('drop') or 0)},'checks':checks,'findings':findings,'historical_suricata_required':False,'production_mutation_performed':False,'traffic_controls_changed':False}
def build():
    units={u:unit_state(u) for u in REQUIRED_SYSTEMD}
    return evaluate(load(CROWD),load(NFT),load(CANARY),load(API_HEALTH),load(CORRELATION),parse_spamhaus(SPAMHAUS),units)
def markdown(d):
    s=d['summary']; lines=['# Edge1 Security Baseline','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Checks: **{s['passed']}/{s['checks']} passed** · Findings: **{s['findings']}**",f"Spamhaus: {s['spamhaus_ipv4']} IPv4 / {s['spamhaus_ipv6']} IPv6 · nftables: {s['nft_rules']} rules / {s['nft_drop_verdicts']} drop verdicts",'', '## Findings','']
    lines += [f"- **{x['severity']} · {x['kind']}** — {x['detail']}" for x in d['findings']] or ['- None.']
    lines += ['','Historical Suricata compatibility telemetry is not required by this baseline; current Suricata service and current sanitized security observations are checked instead.','The bot is read-only and never changes firewall, mail, DNS, IDS, or traffic controls.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/security-baseline/current.md','Edge1 Security Baseline',markdown(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
