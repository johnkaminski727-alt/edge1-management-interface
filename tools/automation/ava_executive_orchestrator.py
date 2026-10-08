#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from server.ava_office_manager import OfficeManagerStore, OfficeManagerError, utc_now
DB=Path('/var/lib/wwcx-ava-office-manager/office-manager.sqlite3')
INVENTORY=Path('/var/www/edge1-status/automation-center/inventory.json')
INBOX=Path('/var/lib/wwcx-ava-office-manager/report-inbox')
STATUS=Path('/var/www/edge1-status/ava/executive-status.json')
ATTN={'attention','failed','error','critical','degraded','unhealthy'}

def slug(v:str)->str:
    s=re.sub(r'[^a-z0-9_.:-]+','-',v.lower()).strip('-')
    if not s or not s[0].isalpha(): s='bot-'+s
    return s[:120]

def department(text:str)->str:
    t=text.lower()
    if any(x in t for x in ('security','spamhaus','suricata','crowdsec','fail2ban','nftables','credential','certificate')): return 'Security'
    if any(x in t for x in ('library','evidence','document','filing','knowledge','catalog')): return 'Records & Library'
    if 'contact' in t: return 'Contacts & Relationships'
    if any(x in t for x in ('accounting','invoice','receipt','bookkeep','finance')): return 'Finance'
    if any(x in t for x in ('mail','reply','communication','message','email')): return 'Communications'
    if any(x in t for x in ('backup','recovery','restore','disaster')): return 'Recovery & Continuity'
    if any(x in t for x in ('dns','vpn','wireguard','network','egress','time authority','storage','api')): return 'Infrastructure & Network'
    if any(x in t for x in ('website','seo','domain','store','catalog consistency')): return 'Business & Web Operations'
    return 'Automation & Operations'

def ceiling(level:str)->str:
    return {'READ-ONLY':'observe','AUTO-STAGE':'prepare','REVIEW-REQUIRED':'prepare','AUTO-FIX':'routine'}.get(level,'observe')

def health_of(timer:dict[str,Any])->str:
    b=timer.get('bot_status') or {}
    state=str(b.get('state') or '').lower()
    if state: return state
    result=str(timer.get('last_result') or 'unknown').lower()
    if result in {'success',''}: return 'healthy'
    return 'attention'

def source_ref(timer:dict[str,Any])->str:
    b=timer.get('bot_status') or {}
    # Synthetic Automation Center status is regenerated with the inventory itself;
    # prefer the underlying service run so an inventory refresh does not become a new report.
    stamp=timer.get('last_run') or b.get('generated_at') or b.get('generated_at_utc') or b.get('checked_at') or 'unknown'
    return f"automation:{timer.get('timer')}:{stamp}"

def severity(timer:dict[str,Any], state:str)->str:
    if state in ATTN:
        s=(timer.get('bot_status') or {}).get('summary') or {}
        if int(s.get('high') or 0)>0: return 'high'
        return 'high' if str(timer.get('last_result') or '').lower() not in {'success',''} else 'medium'
    return 'info'

def resolve_recovered_attention(store:OfficeManagerStore, member_id:str)->bool:
    ref='ava-attention:'+member_id
    with store.connect() as c:
        rows=c.execute("SELECT id,state FROM work_items WHERE source_ref=? AND state NOT IN ('completed','cancelled')",(ref,)).fetchall()
    changed=False
    for row in rows:
        wid=str(row['id']); state=str(row['state'])
        if state=='new':
            store.transition_work_item(wid,'working',actor='ava-executive',note='Team member recovered; closing AVA attention item.')
        store.transition_work_item(wid,'completed',actor='ava-executive',note='Latest team check-in returned to a non-attention state.')
        now=utc_now()
        with store.connect() as c:
            assignments=c.execute("SELECT id FROM executive_assignments WHERE work_item_id=? AND state NOT IN ('completed','cancelled')",(wid,)).fetchall()
            c.execute("UPDATE executive_assignments SET state='completed',updated_at_utc=? WHERE work_item_id=? AND state NOT IN ('completed','cancelled')",(now,wid))
        for a in assignments:
            store._audit('ava-executive','assignment.completed','assignment',str(a['id']),{'work_item_id':wid,'reason':'team member recovered'})
        changed=True
    return changed

def ensure_attention_work(store:OfficeManagerStore, member_id:str, timer:dict[str,Any], report:dict[str,Any])->bool:
    if not report['needs_attention']:
        resolve_recovered_attention(store,member_id)
        return False
    ref='ava-attention:'+member_id
    with store.connect() as c:
        row=c.execute("SELECT id FROM work_items WHERE source_ref=? AND state NOT IN ('completed','cancelled') LIMIT 1",(ref,)).fetchone()
    if row: return False
    title='Review '+str(timer.get('description') or member_id)
    outcome='Assess the bot report, determine the bounded next action, coordinate any dependent team member, and escalate to John only when policy or ambiguity requires it.'
    item=store.create_work_item(title=title,desired_outcome=outcome,source_channel='ava-executive',source_ref=ref,priority='high' if report['severity']=='high' else 'normal',owner='ava',actor='ava-executive')
    store.create_assignment(member_id=member_id,objective='Investigate and report the condition that triggered this AVA executive attention item.',priority='high' if report['severity']=='high' else 'normal',work_item_id=item['id'],state='review',actor='ava-executive')
    return True

def process_direct_inbox(store:OfficeManagerStore)->int:
    INBOX.mkdir(parents=True,exist_ok=True); n=0
    for p in sorted(INBOX.glob('*.json'))[:200]:
        try:
            d=json.loads(p.read_text())
            mid=slug(str(d['member_id']))
            try: store.get_team_member(mid)
            except OfficeManagerError:
                store.upsert_team_member(member_id=mid,display_name=str(d.get('display_name') or mid),department=str(d.get('department') or 'Automation & Operations'),role=str(d.get('role') or 'Direct-report bot'),action_level=str(d.get('action_level') or 'READ-ONLY'),authority_ceiling=str(d.get('authority_ceiling') or 'observe'),health_state=str(d.get('health_state') or 'unknown'))
            ref=str(d.get('source_ref') or 'direct:'+hashlib.sha256(p.read_bytes()).hexdigest())
            store.record_team_report(member_id=mid,report_type=str(d.get('report_type') or 'checkin'),health_state=str(d.get('health_state') or 'unknown'),summary=str(d.get('summary') or 'Direct bot report'),detail=d.get('detail') if isinstance(d.get('detail'),dict) else {},source_ref=ref,needs_attention=bool(d.get('needs_attention')),severity=str(d.get('severity') or 'info'))
            p.rename(p.with_suffix('.processed')); n+=1
        except Exception:
            p.rename(p.with_suffix('.error'))
    return n

def run(db:Path=DB)->dict[str,Any]:
    store=OfficeManagerStore(db)
    data=json.loads(INVENTORY.read_text()) if INVENTORY.is_file() else {'timers':[]}
    registered=reports=new_reports=attention=work_created=0
    for timer in data.get('timers',[]):
        if not timer.get('custom'): continue
        name=str(timer.get('description') or timer.get('timer') or 'Automation bot')
        mid=slug(str((timer.get('bot_status') or {}).get('slug') or timer.get('service') or timer.get('timer')))
        level=str(timer.get('action_level') or 'READ-ONLY'); state=health_of(timer); dept=department(name+' '+mid)
        store.upsert_team_member(member_id=mid,display_name=name,department=dept,role=name,service_unit=timer.get('service'),timer_unit=timer.get('timer'),action_level=level,authority_ceiling=ceiling(level),capabilities=[f"automation.{mid}.observe"],health_state=state,metadata={'timer_enabled':timer.get('enabled'),'timer_state':timer.get('state'),'last_result':timer.get('last_result'),'next_run':timer.get('next_run')})
        registered+=1
        b=timer.get('bot_status') or {}; detail={'timer':timer.get('timer'),'service':timer.get('service'),'action_level':level,'last_result':timer.get('last_result'),'summary':b.get('summary') or {},'status_url':b.get('status_url')}
        sev=severity(timer,state); attn=state in ATTN or sev in {'high','critical'}
        rep=store.record_team_report(member_id=mid,report_type='automation-checkin',health_state=state,summary=f"{name}: {state}",detail=detail,source_ref=source_ref(timer),needs_attention=attn,severity=sev)
        reports+=1; new_reports+=1 if rep.get('new') else 0; attention+=1 if attn else 0
        if ensure_attention_work(store,mid,timer,rep): work_created+=1
    direct=process_direct_inbox(store)
    with store.connect() as c:
        team=int(c.execute('SELECT count(*) FROM executive_team_members WHERE active=1').fetchone()[0]); open_assign=int(c.execute("SELECT count(*) FROM executive_assignments WHERE state NOT IN ('completed','cancelled')").fetchone()[0]); open_work=int(c.execute("SELECT count(*) FROM work_items WHERE state NOT IN ('completed','cancelled')").fetchone()[0]); needs=int(c.execute("SELECT count(*) FROM executive_team_members WHERE active=1 AND health_state IN ('attention','failed','error','critical','degraded','unhealthy')").fetchone()[0])
    out={'contract':'wwcx.ava-executive-orchestrator.v1','generated_at':utc_now(),'team_members':team,'registered_this_run':registered,'reports_seen':reports,'new_reports':new_reports,'direct_reports_processed':direct,'attention_reports_total':needs,'attention_checkins_this_run':attention,'open_assignments':open_assign,'open_work_items':open_work,'work_items_created':work_created,'audit_chain_valid':store.verify_audit_chain(),'execution_authority_expanded':False}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); os.chmod(STATUS,0o644)
    return out

def main():
    a=argparse.ArgumentParser(); a.add_argument('--db',type=Path,default=DB); args=a.parse_args(); print(json.dumps(run(args.db),sort_keys=True))
if __name__=='__main__': main()
