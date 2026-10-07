#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
CFG=ROOT/'config/automation/public-websites.json'
STATUS=Path('/var/www/edge1-status/domain-renewal/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
UA='WWCX-Domain-Renewal-Monitor/1.0'

def parse_time(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None

def domains_from_config(path=CFG):
    data=json.loads(path.read_text()); out=[]
    for row in data.get('sites',[]):
        d=str(row.get('domain') or '').strip().lower().rstrip('.')
        if d and d not in out: out.append(d)
    return out

def lookup(domain):
    url='https://rdap.org/domain/'+domain
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/rdap+json, application/json'})
    with urllib.request.urlopen(req,timeout=20) as r:
        if r.status!=200: raise RuntimeError(f'HTTP {r.status}')
        data=json.loads(r.read(2*1024*1024).decode('utf-8'))
    events={x.get('eventAction'):x.get('eventDate') for x in data.get('events',[]) if isinstance(x,dict)}
    return {'domain':domain,'rdap_name':data.get('ldhName'),'expiration':events.get('expiration'),'registration':events.get('registration'),'statuses':[str(x)[:120] for x in data.get('status',[]) if isinstance(x,str)][:20],'source':'https://rdap.org/domain/'+domain}

def evaluate(rows,now=None):
    now=now or datetime.now(timezone.utc); findings=[]; normalized=[]
    for row in rows:
        item=dict(row); error=item.get('error'); exp=parse_time(item.get('expiration'))
        if error:
            item['state']='unavailable'; item['days_remaining']=None; findings.append({'domain':item['domain'],'severity':'medium','kind':'rdap_unavailable','detail':str(error)[:240],'action_level':'REVIEW-REQUIRED'})
        elif exp is None:
            item['state']='unknown_expiry'; item['days_remaining']=None; findings.append({'domain':item['domain'],'severity':'medium','kind':'expiry_unknown','detail':'RDAP did not provide a valid expiration event.','action_level':'REVIEW-REQUIRED'})
        else:
            days=int((exp-now).total_seconds()//86400); item['days_remaining']=days
            if days<0:
                item['state']='expired'; findings.append({'domain':item['domain'],'severity':'high','kind':'expired','detail':f'RDAP expiration is {item.get("expiration")}.','action_level':'REVIEW-REQUIRED'})
            elif days<=30:
                item['state']='renew_now'; findings.append({'domain':item['domain'],'severity':'high','kind':'expires_30d','detail':f'{days} days remain before expiration.','action_level':'REVIEW-REQUIRED'})
            elif days<=60:
                item['state']='renew_soon'; findings.append({'domain':item['domain'],'severity':'medium','kind':'expires_60d','detail':f'{days} days remain before expiration.','action_level':'AUTO-STAGE'})
            elif days<=180:
                item['state']='plan_renewal'; findings.append({'domain':item['domain'],'severity':'low','kind':'expires_180d','detail':f'{days} days remain before expiration.','action_level':'AUTO-STAGE'})
            else:item['state']='healthy'
        normalized.append(item)
    days=[x['days_remaining'] for x in normalized if isinstance(x.get('days_remaining'),int)]
    state='attention' if any(x['severity']=='high' for x in findings) else 'warning' if any(x['severity']=='medium' for x in findings) else 'healthy'
    return {'contract':'wwcx.domain-renewal.v1','generated_at':now.isoformat(),'state':state,'summary':{'domains':len(normalized),'expiring_180d':sum(isinstance(x.get('days_remaining'),int) and 0<=x['days_remaining']<=180 for x in normalized),'expiring_60d':sum(isinstance(x.get('days_remaining'),int) and 0<=x['days_remaining']<=60 for x in normalized),'expiring_30d':sum(isinstance(x.get('days_remaining'),int) and 0<=x['days_remaining']<=30 for x in normalized),'lookup_failures':sum(x.get('state')=='unavailable' for x in normalized),'nearest_expiry_days':min(days) if days else None,'findings':len(findings),'high':sum(x['severity']=='high' for x in findings),'medium':sum(x['severity']=='medium' for x in findings)},'domains':normalized,'findings':findings,'registrar_mutation_performed':False,'automatic_renewal_authorized':False}

def build():
    rows=[]
    for d in domains_from_config():
        try: rows.append(lookup(d))
        except Exception as e: rows.append({'domain':d,'error':f'{type(e).__name__}: {str(e)[:180]}','source':'https://rdap.org/domain/'+d})
    return evaluate(rows)
def markdown(d):
    s=d['summary']; lines=['# Domain Renewal Monitor','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Domains: **{s['domains']}** · nearest expiry: **{s['nearest_expiry_days']} days**",'', '## Domains','']
    for x in sorted(d['domains'],key=lambda z:(z.get('days_remaining') is None,z.get('days_remaining') if z.get('days_remaining') is not None else 999999,z['domain'])):
        lines.append(f"- **{x['domain']}** — {x.get('expiration') or 'expiration unavailable'} — {x.get('days_remaining') if x.get('days_remaining') is not None else 'unknown'} days — {x.get('state')}")
    lines += ['','## Findings',''] + ([f"- **{x['severity']} · {x['domain']}** — {x['detail']}" for x in d['findings']] or ['- None.'])
    lines += ['','RDAP observation only. This bot does not log into registrars, alter nameservers, change contacts, or renew domains.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/domain-renewal/current.md','Domain Renewal Monitor',markdown(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
