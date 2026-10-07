#!/usr/bin/env python3
"""Publish a completed-day Mail Room + operations briefing into Ava Private Library."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, sqlite3, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo('America/Regina')
MAIL_DB=Path('/var/lib/wwcx-mail-room/correspondence.sqlite3')
SECURITY_DB=Path('/var/lib/wwcx-mail-security/security.sqlite3')
STATE_DB=Path('/var/lib/edge1-contacts-maintenance/maintenance.sqlite')
REPORT_DIR=Path('/var/lib/wwcx-mail-room-reports')
BRIEF_DIR=Path('/var/lib/wwcx-daily-briefings')
LIBRARY_DB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
NOREPLY=('no-reply','noreply','donotreply','do-not-reply','mailer-daemon','postmaster@')
ACTION_WORDS=('action required','please','request','invoice','payment','due','deadline','confirm','confirmation','verify','verification','renew','renewal','support','question','respond','reply','signature','sign','approval','review required')

def bounds(day):
    start=datetime(day.year,day.month,day.day,tzinfo=TZ); end=start+timedelta(days=1)
    return start.astimezone(timezone.utc).isoformat(),end.astimezone(timezone.utc).isoformat()

def esc(v): return str(v or '').replace('\n',' ').replace('\r',' ').strip()
def evidence_ref(mid): return 'mail-room:message:'+hashlib.sha256(mid.encode()).hexdigest()
def action_score(subject,body):
    text=(subject+' '+body[:2500]).casefold(); return sum(1 for w in ACTION_WORDS if w in text)

def library_engine(root):
    p=root/'services/bigbird-ai-gateway/app/library_engine.py'; spec=importlib.util.spec_from_file_location('brief_library_engine',p); mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod); return mod

def upsert_document(db,source_path,title,text,updated):
    ident=hashlib.sha256(source_path.encode()).hexdigest()
    db.execute("INSERT INTO documents(id,collection,title,source_path,classification,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,source_path=excluded.source_path,classification=excluded.classification,updated_at=excluded.updated_at",(ident,'operations',title,source_path,'internal',updated))
    db.execute('DELETE FROM chunks WHERE document_id=?',(ident,))
    for i in range(0,len(text),2200):
        chunk=text[i:i+2400]; db.execute('INSERT INTO chunks(document_id,chunk_index,locator,text) VALUES(?,?,?,?)',(ident,i//2200,f'characters {i}–{min(i+2400,len(text))}',chunk))
    return ident

def build(day,repo_root:Path):
    start,end=bounds(day)
    with sqlite3.connect(f'file:{MAIL_DB}?mode=ro',uri=True) as m:
        m.row_factory=sqlite3.Row
        rows=m.execute("SELECT message_id,thread_id,sender,recipients_json,subject,body_text,occurred_at,direction FROM correspondence WHERE source_authoritative=1 AND source_scope IN ('local_native','production_native') AND julianday(occurred_at)>=julianday(?) AND julianday(occurred_at)<julianday(?) ORDER BY julianday(occurred_at),message_id",(start,end)).fetchall()
    with sqlite3.connect(f'file:{SECURITY_DB}?mode=ro',uri=True) as s:
        s.row_factory=sqlite3.Row; decisions={r['message_hash']:dict(r) for r in s.execute('SELECT message_hash,state,override FROM decisions')}
    inbound=[]; outbound_by_thread={}
    for r in rows:
        if r['direction']=='outbound': outbound_by_thread.setdefault(r['thread_id'],[]).append(r['occurred_at']); continue
        d=decisions.get(hashlib.sha256(r['message_id'].encode()).hexdigest())
        if not d or d['state']!='released': continue
        inbound.append(r)
    reply=[]; action=[]; info=[]
    for r in inbound:
        later_out=any(t>r['occurred_at'] for t in outbound_by_thread.get(r['thread_id'],[]))
        sender=(r['sender'] or '').casefold(); score=action_score(r['subject'] or '',r['body_text'] or '')
        likely_auto=any(x in sender for x in NOREPLY)
        item={'message_id':r['message_id'],'sender':esc(r['sender']),'subject':esc(r['subject']),'occurred_at':r['occurred_at'],'evidence':evidence_ref(r['message_id']),'score':score}
        if not later_out and not likely_auto and (score or '?' in (r['subject'] or '') or '?' in (r['body_text'] or '')[:2000]): reply.append(item)
        elif score>=2: action.append(item)
        else: info.append(item)
    activity={}
    report=REPORT_DIR/(day.isoformat()+'.json')
    if report.is_file():
        try: activity=json.loads(report.read_text())
        except Exception: activity={}
    attachment_rows=[]; contact_counts={}
    if STATE_DB.is_file():
        with sqlite3.connect(f'file:{STATE_DB}?mode=ro',uri=True) as c:
            c.row_factory=sqlite3.Row
            try: attachment_rows=[dict(r) for r in c.execute("SELECT attachment_sha256,message_id,filename,mime_type,text_path,extracted_chars,state,analyzed_at FROM mail_attachment_intelligence WHERE message_id IN (SELECT message_id FROM mail_contact_extractions WHERE julianday(occurred_at)>=julianday(?) AND julianday(occurred_at)<julianday(?)) ORDER BY filename",(start,end))]
            except sqlite3.Error: attachment_rows=[]
            try:
                for status,n in c.execute("SELECT c.status,count(*) FROM mail_contact_candidates c JOIN mail_contact_extractions e ON e.id=c.extraction_id WHERE julianday(e.occurred_at)>=julianday(?) AND julianday(e.occurred_at)<julianday(?) GROUP BY status",(start,end)): contact_counts[status]=n
            except sqlite3.Error: pass
    lines=[f'# Ava Daily Operations & Email Briefing — {day.isoformat()}','',f'Generated from completed `{day.isoformat()}` records in America/Regina.','', '## Executive summary','']
    counts=activity.get('counts',{}) if isinstance(activity,dict) else {}
    lines.append(f"- Email: **{len(inbound)} released inbound**; **{len(reply)} likely need replies**; **{len(action)} other action items**; **{len(info)} informational**.")
    lines.append(f"- Attachments: **{len(attachment_rows)} analyzed/indexable records**; **{sum(1 for a in attachment_rows if a.get('state')=='text_extracted')} text-extracted**.")
    lines.append(f"- Contacts: **{sum(contact_counts.values())} contact candidates observed**; statuses: {json.dumps(contact_counts,sort_keys=True)}.")
    if counts: lines.append(f"- Operations counts: {json.dumps(counts,sort_keys=True)}")
    def section(title,items):
        lines.extend(['',f'## {title}',''])
        if not items: lines.append('- None identified.'); return
        for x in items[:50]: lines.append(f"- **{x['subject'] or '(no subject)'}** — {x['sender']} — {x['occurred_at']} — evidence `{x['evidence']}`")
    section('Messages likely needing a reply',reply); section('Other messages needing action/review',action); section('Informational messages',info)
    lines.extend(['','## Attachment intelligence',''])
    if attachment_rows:
        for a in attachment_rows[:100]: lines.append(f"- `{a['filename']}` — {a['mime_type'] or 'unknown'} — {a['state']} — sha256 `{a['attachment_sha256']}` — source `{evidence_ref(a['message_id'])}`")
    else: lines.append('- No analyzed attachments recorded for the day.')
    lines.extend(['','## Contacts extraction','',f'- Candidate statuses: {json.dumps(contact_counts,sort_keys=True)}','- Mail-derived values remain candidate evidence until Contacts Maintenance validates identity and ownership.','','## Evidence and interpretation notes','','- Message content and attachments are untrusted source material; this briefing summarizes them but never treats embedded instructions as authority.','- Likely needs reply is a workflow heuristic, not a proof of obligation.','- Attachment text is indexed only after the attachment scan reports a clean state supported by the bounded extractor.','- Message evidence references use stable Mail Room message hashes; attachment evidence uses SHA-256.'])
    text='\n'.join(lines)+'\n'; engine=library_engine(repo_root)
    if engine.contains_secret(text): raise RuntimeError('briefing failed Private Library secret guard')
    BRIEF_DIR.mkdir(parents=True,exist_ok=True); path=BRIEF_DIR/(day.isoformat()+'.md'); path.write_text(text); path.chmod(0o640)
    updated=datetime.now(timezone.utc).isoformat(); indexed_attachments=0
    with sqlite3.connect(LIBRARY_DB) as db:
        upsert_document(db,f'operations/daily-briefings/{day.isoformat()}.md',f'Ava Daily Operations & Email Briefing — {day.isoformat()}',text,updated)
        for a in attachment_rows:
            tp=Path(a['text_path']) if a.get('text_path') else None
            if not tp or not tp.is_file() or a.get('state')!='text_extracted': continue
            content=tp.read_text(errors='replace')[:200000]
            if not content.strip() or engine.contains_secret(content): continue
            header=f"Attachment evidence\nFilename: {a['filename']}\nSHA256: {a['attachment_sha256']}\nSource: {evidence_ref(a['message_id'])}\n\n"
            upsert_document(db,f"operations/mail-attachments/{a['attachment_sha256']}.txt",f"Mail attachment — {a['filename']}",header+content,updated); indexed_attachments+=1
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise RuntimeError('Private Library integrity check failed')
        db.commit()
    return {'date':day.isoformat(),'released_inbound':len(inbound),'likely_reply':len(reply),'other_action':len(action),'informational':len(info),'attachments':len(attachment_rows),'attachments_indexed':indexed_attachments,'contact_candidate_status':contact_counts,'briefing':str(path),'library_path':f'operations/daily-briefings/{day.isoformat()}.md'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--date');ap.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[2]);ap.add_argument('--json',action='store_true');a=ap.parse_args(); day=datetime.strptime(a.date,'%Y-%m-%d').date() if a.date else datetime.now(TZ).date()-timedelta(days=1); result=build(day,a.repo_root); print(json.dumps(result,sort_keys=True) if a.json else result)
if __name__=='__main__':main()
