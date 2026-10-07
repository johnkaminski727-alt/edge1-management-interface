#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
STATUS=Path('/var/www/edge1-status/outstanding-actions/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
MAINT=Path('/var/lib/edge1-contacts-maintenance/maintenance.sqlite')
MAIL=Path('/var/lib/wwcx-mail-room/correspondence.sqlite3')
SEC=Path('/var/lib/wwcx-mail-security/security.sqlite3')

def load(path):
    try:return json.loads(path.read_text())
    except Exception:return {}
def midhash(v): return hashlib.sha256(v.encode()).hexdigest()
def age_hours(value):
    try:return (datetime.now(timezone.utc)-datetime.fromisoformat(str(value).replace('Z','+00:00'))).total_seconds()/3600
    except Exception:return None

def mail_actions(limit=40):
    if not MAIL.is_file() or not SEC.is_file(): return [],'unavailable'
    cutoff=(datetime.now(timezone.utc)-timedelta(days=14)).isoformat(); released=set()
    with sqlite3.connect(f'file:{SEC}?mode=ro',uri=True) as s:
        released={r[0] for r in s.execute("SELECT message_hash FROM decisions WHERE state='released'")}
    with sqlite3.connect(f'file:{MAIL}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute("""SELECT message_id,thread_id,sender,subject,body_text,occurred_at,direction FROM correspondence
          WHERE source_authoritative=1 AND source_scope IN ('local_native','production_native') AND julianday(occurred_at)>=julianday(?)
          ORDER BY julianday(occurred_at) DESC LIMIT 1200""",(cutoff,)).fetchall()
    outbound_latest={}
    for r in rows:
        if r['direction']=='outbound': outbound_latest[r['thread_id']]=max(outbound_latest.get(r['thread_id'],'') or '',r['occurred_at'] or '')
    actions=[]
    reply_words=('please','could you','can you','let me know','reply','respond','confirm','question','?')
    action_words=('action required','payment declined','past due','pre-suspension','suspension','security alert','no longer recoverable','account locked','amount due','due date','e-bill is ready','request is ready')
    exclude=('auth check','dkim','commissioning','test message','acceptance','pilot')
    promotional=('unsubscribe','last chance','% off','discount','special offer','launches in','privacy policy','terms of service','premium offer')
    automated_localparts=('noreply','no-reply','no_reply','notifications','notices','ebill','recommendations','payments-noreply')
    for r in rows:
        if r['direction']!='inbound' or midhash(r['message_id']) not in released: continue
        subject=(r['subject'] or '').strip(); body=(r['body_text'] or '')[:4000]; text=(subject+' '+body).lower(); sender=(r['sender'] or '').lower(); local=sender.split('@',1)[0]
        if any(x in text for x in exclude) or any(x in text for x in promotional): continue
        automated=any(x in local for x in automated_localparts)
        needs_action=any(x in text for x in action_words)
        needs_reply=not automated and any(x in text for x in reply_words)
        if not (needs_action or needs_reply): continue
        if needs_reply and outbound_latest.get(r['thread_id'],'') > (r['occurred_at'] or ''): continue
        priority='high' if any(x in text for x in ('urgent','asap','deadline','past due','pre-suspension','suspension','payment declined','action required')) else 'medium'
        detail=(f"Reply likely needed to {r['sender']}" if needs_reply else f"Review/action likely needed from automated message by {r['sender']}")
        actions.append({'id':'mail:'+midhash(r['message_id']),'source':'mail','priority':priority,'title':subject or '(no subject)','detail':detail,'occurred_at':r['occurred_at'],'evidence':'mail-room:message:'+midhash(r['message_id']),'action_level':'REVIEW-REQUIRED'})
        if len(actions)>=limit: break
    return actions,'available'

def contacts_actions():
    if not MAINT.is_file(): return [],'unavailable'
    with sqlite3.connect(f'file:{MAINT}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        review=db.execute("SELECT COUNT(*) FROM candidate_changes WHERE status='pending' AND action_level='REVIEW_REQUIRED'").fetchone()[0]
        high=db.execute("SELECT COUNT(*) FROM maintenance_findings WHERE status='open' AND severity='high'").fetchone()[0]
        enrich=db.execute("SELECT COUNT(*) FROM enrichment_queue WHERE status='pending'").fetchone()[0]
    out=[]
    if review: out.append({'id':'contacts:review','source':'contacts','priority':'medium','title':f'{review} Contacts changes need review','detail':'Contacts Maintenance has evidence-backed changes awaiting review.','action_level':'REVIEW-REQUIRED'})
    if high: out.append({'id':'contacts:high-findings','source':'contacts','priority':'high','title':f'{high} high-severity Contacts findings','detail':'Review high-severity identity/evidence findings.','action_level':'REVIEW-REQUIRED'})
    if enrich: out.append({'id':'contacts:enrichment','source':'contacts','priority':'low','title':f'{enrich} Contacts enrichment tasks pending','detail':'Background enrichment queue has pending work.','action_level':'AUTO-STAGE'})
    return out,'available'

def build():
    actions=[]; sources={}
    ma,ms=mail_actions(); actions+=ma; sources['mail']=ms
    ca,cs=contacts_actions(); actions+=ca; sources['contacts']=cs
    incidents=load(Path('/var/www/edge1-status/operations-incidents.json')); ih=age_hours(incidents.get('generated_at'))
    sources['incidents']='stale' if ih is None or ih>1 else 'available'
    if sources['incidents']=='available':
        for x in incidents.get('active_incidents',[])[:30]: actions.append({'id':'incident:'+str(x.get('id')),'source':'operations','priority':'high' if x.get('severity') in ('critical','error') else 'medium','title':f"{x.get('component','Operations')}: {x.get('detail','attention required')}",'detail':x.get('recommendation') or 'Review active incident.','occurred_at':x.get('detected_at'),'action_level':'REVIEW-REQUIRED'})
    automation=load(Path('/var/www/edge1-status/automation-center/inventory.json')); sources['automation']='available' if automation else 'unavailable'
    for t in automation.get('timers',[]):
        if t.get('last_result') not in (None,'success') or t.get('state')=='failed': actions.append({'id':'automation:'+str(t.get('timer')),'source':'automation','priority':'high','title':f"Automation problem: {t.get('timer')}",'detail':f"state={t.get('state')} result={t.get('last_result')}",'action_level':'REVIEW-REQUIRED'})
    backup=load(Path('/var/www/edge1-status/backup-verification/status.json'))
    if backup:
        sources['disaster_recovery']='available'
        if backup.get('state')!='healthy': actions.append({'id':'backup:posture','source':'backup','priority':'high','title':'Backup posture needs attention','detail':'Backup verification reports attention is required.','action_level':'REVIEW-REQUIRED'})
    else:
        dr=load(Path('/var/www/edge1-status/disaster-recovery/status.json')); dh=age_hours(dr.get('checked_utc')); sources['disaster_recovery']='stale' if dh is None or dh>36 else 'available'
        if not dr.get('remote_present') or not dr.get('remote_checksum_verified') or sources['disaster_recovery']=='stale': actions.append({'id':'backup:posture','source':'backup','priority':'high','title':'Backup posture needs attention','detail':'Off-site backup evidence is missing, stale, or checksum verification is not current.','action_level':'REVIEW-REQUIRED'})
    order={'high':0,'medium':1,'low':2}; actions.sort(key=lambda x:(order.get(x['priority'],9),x['source'],x['title']))
    counts={p:sum(a['priority']==p for a in actions) for p in ('high','medium','low')}
    return {'contract':'wwcx.outstanding-actions.v1','generated_at':utcnow(),'summary':{'total':len(actions),**counts},'sources':sources,'actions':actions[:200],'mutation_performed':False}
def markdown(data):
    lines=['# Current Outstanding Actions','',f"Generated: {data['generated_at']}",f"Total: {data['summary']['total']} · High: {data['summary']['high']} · Medium: {data['summary']['medium']} · Low: {data['summary']['low']}",'']
    for p in ('high','medium','low'):
        lines += [f'## {p.title()} priority','']
        rows=[a for a in data['actions'] if a['priority']==p]
        lines += [f"- **{a['title']}** — {a['detail']} — source `{a['source']}`" for a in rows] or ['- None.']
        lines.append('')
    lines += ['## Safety','','This queue is advisory. It does not send messages, execute tasks, change contacts, restore backups, or mutate services.']
    return '\n'.join(lines)+'\n'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=STATUS); ap.add_argument('--no-library',action='store_true'); a=ap.parse_args(); data=build(); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(data,indent=2)+'\n'); a.output.chmod(0o644)
    if not a.no_library: upsert_library_document(LIB,ROOT,'operations/outstanding-actions/current.md','Current Outstanding Actions',markdown(data))
    print(json.dumps(data['summary'],sort_keys=True))
if __name__=='__main__': main()
