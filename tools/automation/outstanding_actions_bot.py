#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3
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
def normalized_subject(value):
    text=' '.join(str(value or '').strip().casefold().split())
    while True:
        newer=re.sub(r'^(?:re|fw|fwd):\s*','',text,count=1)
        if newer==text: break
        text=newer
    return text.strip(' .!-_')
def automated_notice_family(subject, text=''):
    combined=(' '.join([str(subject or ''),str(text or '')])).casefold()
    if any(x in combined for x in ('past due','pre-suspension','suspension','payment declined','amount due','e-bill','balance on your account')):
        return 'billing-account'
    if any(x in combined for x in ('security alert','no longer recoverable','account locked','sign in to your google account','google account')):
        return 'account-access-security'
    if any(x in combined for x in ('request is ready','request ready','ready for pickup','ready for pick up')):
        return 'request-ready'
    return normalized_subject(subject)

def age_hours(value):
    try:return (datetime.now(timezone.utc)-datetime.fromisoformat(str(value).replace('Z','+00:00'))).total_seconds()/3600
    except Exception:return None
def keep_active_mail_action(priority, occurred_at, routine_days=7):
    age=age_hours(occurred_at)
    if age is None:return True
    return priority=='high' or age <= routine_days*24

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
    exclude=('auth check','outbound check','dkim','commissioning','test message','acceptance','pilot')
    promotional=('unsubscribe','last chance','% off','discount','special offer','launches in','privacy policy','terms of service','premium offer')
    automated_localparts=('noreply','no-reply','no_reply','notifications','notices','ebill','recommendations','payments-noreply')
    seen_action_threads=set(); automated_groups={}
    for r in rows:
        if r['direction']!='inbound' or midhash(r['message_id']) not in released: continue
        subject=(r['subject'] or '').strip(); body=(r['body_text'] or '')[:4000]; text=(subject+' '+body).lower(); sender=(r['sender'] or '').lower(); local=sender.split('@',1)[0]
        if any(x in text for x in exclude) or any(x in text for x in promotional): continue
        automated=any(x in local for x in automated_localparts)
        needs_action=any(x in text for x in action_words)
        needs_reply=not automated and any(x in text for x in reply_words)
        if not (needs_action or needs_reply): continue
        if needs_reply and outbound_latest.get(r['thread_id'],'') > (r['occurred_at'] or ''): continue
        thread_key=(r['thread_id'] or '').strip()
        if thread_key and thread_key in seen_action_threads: continue
        group_key=None
        if automated:
            family=automated_notice_family(subject,text)
            group_key=(sender,family) if family else None
            if group_key and group_key in automated_groups:
                existing=automated_groups[group_key]
                existing['evidence_count']=int(existing.get('evidence_count',1))+1
                evidence='mail-room:message:'+midhash(r['message_id'])
                existing.setdefault('related_evidence',[]).append(evidence)
                continue
        if thread_key: seen_action_threads.add(thread_key)
        priority='high' if any(x in text for x in ('urgent','asap','deadline','past due','pre-suspension','suspension','payment declined','action required')) else 'medium'
        if not keep_active_mail_action(priority,r['occurred_at']): continue
        detail=(f"Reply likely needed to {r['sender']}" if needs_reply else f"Review/action likely needed from automated message by {r['sender']}")
        evidence='mail-room:message:'+midhash(r['message_id'])
        action_id='mail:'+midhash(r['message_id'])
        extra={}
        if automated and group_key:
            stable=hashlib.sha256((group_key[0]+'|'+group_key[1]).encode()).hexdigest()
            action_id='mail-group:'+stable
            extra={'evidence_count':1,'related_evidence':[evidence],'notice_family':group_key[1]}
        action={'id':action_id,'source':'mail','priority':priority,'title':subject or '(no subject)','detail':detail,'occurred_at':r['occurred_at'],'evidence':evidence,'action_level':'REVIEW-REQUIRED',**extra}
        actions.append(action)
        if automated and group_key: automated_groups[group_key]=action
        if len(actions)>=limit: break
    for action in actions:
        count=int(action.get('evidence_count',1))
        if count>1:
            action['detail']=f"{count} related automated notices grouped together; review the latest notice and supporting evidence."
    return actions,'available'

def contacts_actions():
    if not MAINT.is_file(): return [],'unavailable'
    with sqlite3.connect(f'file:{MAINT}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        review=db.execute("SELECT COUNT(*) FROM candidate_changes WHERE status='pending' AND action_level='REVIEW_REQUIRED'").fetchone()[0]
        high=db.execute("SELECT COUNT(*) FROM maintenance_findings WHERE status='open' AND severity='high'").fetchone()[0]
        enrich=db.execute("SELECT COUNT(*) FROM enrichment_queue WHERE status='pending'").fetchone()[0]
        enrich_review=db.execute("SELECT COUNT(*) FROM enrichment_queue WHERE status='review_required'").fetchone()[0]
    out=[]
    if review: out.append({'id':'contacts:review','source':'contacts','priority':'medium','title':f'{review} Contacts changes need review','detail':'Contacts Maintenance has evidence-backed changes awaiting review.','action_level':'REVIEW-REQUIRED'})
    if high: out.append({'id':'contacts:high-findings','source':'contacts','priority':'high','title':f'{high} high-severity Contacts findings','detail':'Review high-severity identity/evidence findings.','action_level':'REVIEW-REQUIRED'})
    if enrich_review: out.append({'id':'contacts:enrichment-review','source':'contacts','priority':'medium','title':f'{enrich_review} Contacts enrichment research results need review','detail':'First-party public research produced evidence-backed candidates; no contact values were changed automatically.','action_level':'REVIEW-REQUIRED'})
    if enrich: out.append({'id':'contacts:enrichment','source':'contacts','priority':'low','title':f'{enrich} Contacts enrichment tasks pending','detail':'Background enrichment queue has pending work.','action_level':'AUTO-STAGE'})
    return out,'available'

def build():
    actions=[]; sources={}
    ma,ms=mail_actions(); sources['mail']=ms
    reply_status=load(Path('/var/www/edge1-status/reply-suggestions/status.json')); sources['reply_suggestions']='available' if reply_status else 'unavailable'
    suggested={x.get('evidence') for x in (reply_status.get('items') or []) if x.get('evidence')}
    for item in ma:
        if item.get('evidence') in suggested:
            item['detail']=(item.get('detail') or 'Reply likely needed') + '; Ava reply suggestion is staged for review.'
            item['reply_suggestion_available']=True
    actions+=ma
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
    drift=load(Path('/var/www/edge1-status/drift-monitor/status.json')); sources['drift']='available' if drift else 'unavailable'
    for x in drift.get('findings',[])[:30]:
        actions.append({'id':'drift:'+str(x.get('kind')),'source':'drift','priority':'high' if x.get('severity') in ('critical','high') else 'medium','title':'Drift: '+str(x.get('kind','finding')).replace('_',' '),'detail':x.get('detail') or 'Review detected drift.','action_level':x.get('action_level','REVIEW-REQUIRED')})
    cert=load(Path('/var/www/edge1-status/certificate-expiry/status.json')); sources['certificates']='available' if cert else 'unavailable'
    if cert.get('state')=='attention': actions.append({'id':'certificates:expiry','source':'certificates','priority':'high','title':'Certificate or key expiry needs attention','detail':f"{cert.get('attention_count',0)} certificate/key items are inside the warning window.",'action_level':'REVIEW-REQUIRED'})
    domains=load(Path('/var/www/edge1-status/domain-renewal/status.json')); sources['domain_renewal']='available' if domains else 'unavailable'
    if domains.get('state') in {'attention','warning'}: actions.append({'id':'domains:renewal','source':'domain-renewal','priority':'high' if domains.get('state')=='attention' else 'medium','title':'Domain registration renewal needs attention','detail':f"Nearest managed domain expiry is {(domains.get('summary') or {}).get('nearest_expiry_days')} days; {(domains.get('summary') or {}).get('findings',0)} renewal findings.",'action_level':'REVIEW-REQUIRED'})
    storage=load(Path('/var/www/edge1-status/storage-health/status.json')); sources['storage']='available' if storage else 'unavailable'
    if storage.get('state')=='attention': actions.append({'id':'storage:health','source':'storage','priority':'high','title':'Storage or database health needs attention','detail':'Storage/database health monitor reported an attention state.','action_level':'REVIEW-REQUIRED'})
    updates=load(Path('/var/www/edge1-status/update-readiness/status.json')); sources['update_readiness']='available' if updates else 'unavailable'
    us=(updates.get('summary') or {})
    if int(us.get('persistent_failed_units') or 0): actions.append({'id':'maintenance:failed-units','source':'update-readiness','priority':'high','title':'Persistent failed systemd units need review','detail':f"{us.get('persistent_failed_units')} persistent units are failed; transient test units are excluded.",'action_level':'REVIEW-REQUIRED'})
    if us.get('reboot_required'): actions.append({'id':'maintenance:reboot','source':'update-readiness','priority':'high','title':'Edge1 reboot is required to complete maintenance','detail':'A reboot-required marker is present. Schedule a guarded reboot and post-reboot verification.','action_level':'REVIEW-REQUIRED'})
    if int(us.get('security_updates') or 0): actions.append({'id':'maintenance:security-updates','source':'update-readiness','priority':'medium','title':'Security package updates are ready to stage','detail':f"{us.get('security_updates')} security-channel packages are pending; {us.get('kernel_updates',0)} are kernel-related.",'action_level':'AUTO-STAGE'})
    mailhealth=load(Path('/var/www/edge1-status/mail-domain-health/status.json')); sources['mail_domain_health']='available' if mailhealth else 'unavailable'
    if mailhealth.get('state')=='attention': actions.append({'id':'mail-domain:health','source':'mail-domain','priority':'high','title':'Mail or domain health needs attention','detail':'; '.join(mailhealth.get('warnings') or ['Mail/domain health reported attention.']),'action_level':'REVIEW-REQUIRED'})
    for item in mailhealth.get('followups',[])[:10]: actions.append({'id':'mail-domain:followup:'+str(item),'source':'mail-domain','priority':'low','title':'Mail/DNS follow-up: '+str(item).replace('_',' '),'detail':'Tracked follow-up from Mail & Domain Health; service is not currently degraded.','action_level':'AUTO-STAGE'})
    knowledge=load(Path('/var/www/edge1-status/knowledge-consolidation/status.json')); sources['knowledge']='available' if knowledge else 'unavailable'
    if int(knowledge.get('review_items') or 0)>0: actions.append({'id':'knowledge:consolidation','source':'knowledge','priority':'low','title':f"{knowledge.get('review_items')} Private Library consolidation groups need review",'detail':'Knowledge Consolidation found duplicate/title groups; no documents were changed.','action_level':'REVIEW-REQUIRED'})
    accounting=load(Path('/var/www/edge1-status/accounting-intake/status.json')); sources['accounting_intake']='available' if accounting else 'unavailable'
    account_review=int((accounting.get('review_status') or {}).get('review_required',0)); account_dupes=int(accounting.get('possible_duplicate_items') or 0)
    if account_review: actions.append({'id':'accounting:review','source':'accounting','priority':'medium','title':f'{account_review} accounting documents need review','detail':'Invoice intake staged evidence-backed records for review; no payment action is authorized.','action_level':'REVIEW-REQUIRED'})
    if account_dupes: actions.append({'id':'accounting:duplicates','source':'accounting','priority':'medium','title':f'{account_dupes} possible duplicate accounting documents','detail':'Potential duplicates share invoice number and amount across distinct attachment hashes.','action_level':'REVIEW-REQUIRED'})
    credentials=load(Path('/var/www/edge1-status/credential-lifecycle/status.json')); sources['credential_lifecycle']='available' if credentials else 'unavailable'
    if credentials.get('state')=='attention': actions.append({'id':'credentials:lifecycle','source':'credentials','priority':'high','title':'Credential lifecycle needs review','detail':f"{credentials.get('attention_count',0)} credential metadata items are missing, old, or have permission concerns. Secret contents were not read.",'action_level':'REVIEW-REQUIRED'})
    learning=load(Path('/var/www/edge1-status/mail-learning/status.json')); sources['mail_learning']='available' if learning else 'unavailable'
    for i,item in enumerate((learning.get('recommendations') or [])[:5]): actions.append({'id':f'mail-learning:{i}','source':'mail-learning','priority':'low','title':'Mail learning review','detail':str(item),'action_level':'REVIEW-REQUIRED'})
    avaq=load(Path('/var/www/edge1-status/ava-quality/status.json')); sources['ava_quality']='available' if avaq else 'unavailable'
    if avaq.get('state')=='attention':
        metrics=avaq.get('metrics') or {}
        actions.append({'id':'ava:quality','source':'ava-quality','priority':'medium','title':'Ava routing/evidence quality needs review','detail':f"{metrics.get('read_routed_zero_evidence',0)} read-routed completions had zero evidence; {metrics.get('failed',0)} failed requests in the QA window.",'action_level':'REVIEW-REQUIRED'})
    watchdog=load(Path('/var/www/edge1-status/automation-watchdog/status.json')); sources['automation_watchdog']='available' if watchdog else 'unavailable'
    if watchdog.get('state') in {'attention','warning'}: actions.append({'id':'automation:watchdog','source':'automation-watchdog','priority':'high' if watchdog.get('state')=='attention' else 'medium','title':'Background automation watchdog needs attention','detail':f"{(watchdog.get('summary') or {}).get('findings',0)} automation freshness/execution findings.",'action_level':'REVIEW-REQUIRED'})
    evidence=load(Path('/var/www/edge1-status/evidence-integrity/status.json')); sources['evidence_integrity']='available' if evidence else 'unavailable'
    if evidence.get('state') in {'attention','warning'}: actions.append({'id':'evidence:integrity','source':'evidence-integrity','priority':'high' if evidence.get('state')=='attention' else 'medium','title':'Evidence integrity needs review','detail':f"{(evidence.get('summary') or {}).get('findings',0)} evidence/provenance findings.",'action_level':'REVIEW-REQUIRED'})
    apihealth=load(Path('/var/www/edge1-status/api-surface-health/status.json')); sources['api_surface_health']='available' if apihealth else 'unavailable'
    if apihealth.get('state') in {'attention','warning'}: actions.append({'id':'api:surface-health','source':'api-surface-health','priority':'high' if apihealth.get('state')=='attention' else 'medium','title':'API surface health needs review','detail':f"{(apihealth.get('summary') or {}).get('findings',0)} listener/service/access-boundary findings.",'action_level':'REVIEW-REQUIRED'})
    baseline=load(Path('/var/www/edge1-status/security-baseline/status.json')); sources['security_baseline']='available' if baseline else 'unavailable'
    if baseline.get('state') in {'attention','warning'}: actions.append({'id':'security:baseline','source':'security-baseline','priority':'high' if baseline.get('state')=='attention' else 'medium','title':'Security baseline needs attention','detail':f"{(baseline.get('summary') or {}).get('findings',0)} baseline checks require review.",'action_level':'REVIEW-REQUIRED'})
    lifecycle=load(Path('/var/www/edge1-status/action-lifecycle/status.json')); sources['action_lifecycle']='available' if lifecycle else 'unavailable'
    heal=load(Path('/var/www/edge1-status/service-self-heal/status.json')); sources['self_heal']='available' if heal else 'unavailable'
    for row in heal.get('services',[]):
        if row.get('action')=='restart_failed' or row.get('after')=='failed': actions.append({'id':'self-heal:'+str(row.get('unit')),'source':'self-heal','priority':'high','title':'Service self-heal failed: '+str(row.get('unit')),'detail':'Bounded restart did not restore this allowlisted service.','action_level':'REVIEW-REQUIRED'})
    websites=load(Path('/var/www/edge1-status/website-health/status.json')); sources['website_health']='available' if websites else 'unavailable'
    if websites.get('state') in {'attention','warning'}:
        actions.append({'id':'websites:health','source':'websites','priority':'high' if websites.get('state')=='attention' else 'medium','title':'Public website health needs attention','detail':f"{len(websites.get('issues') or [])} website health issues detected.",'action_level':'REVIEW-REQUIRED'})
    seo=load(Path('/var/www/edge1-status/seo-audit/status.json')); sources['seo_audit']='available' if seo else 'unavailable'
    if seo.get('state') in {'attention','warning'}:
        summary=seo.get('summary') or {}; actions.append({'id':'websites:seo','source':'seo','priority':'high' if summary.get('high') else 'medium','title':'SEO/crawl audit needs attention','detail':f"{summary.get('issues',0)} crawl/metadata issues detected across {summary.get('pages_checked',0)} pages.",'action_level':'AUTO-STAGE'})
    catalog=load(Path('/var/www/edge1-status/catalog-consistency/status.json')); sources['catalog_consistency']='available' if catalog else 'unavailable'
    if catalog.get('state') in {'attention','warning'}:
        summary=catalog.get('summary') or {}; actions.append({'id':'store:catalog-consistency','source':'catalog','priority':'high' if catalog.get('state')=='attention' else 'medium','title':'Store catalog consistency needs attention','detail':f"{summary.get('findings',0)} live-vs-fallback catalog differences detected.",'action_level':'AUTO-STAGE'})
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
