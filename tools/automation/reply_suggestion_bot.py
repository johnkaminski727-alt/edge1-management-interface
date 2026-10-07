#!/usr/bin/env python3
"""Stage Ava-generated reply suggestions for unresolved released human mail.

This bot never sends mail and never writes Mail Room drafts. Suggestions are kept
in a private root-only state database and an internal Ava Private Library document.
The public status projection exposes counts and hashed evidence identifiers only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from server.mail_room_ava import AvaMailAssistant
from tools.automation.automation_common import utcnow, upsert_library_document

MAIL=Path('/var/lib/wwcx-mail-room/correspondence.sqlite3')
SECURITY=Path('/var/lib/wwcx-mail-security/security.sqlite3')
STATE=Path('/var/lib/edge1-reply-suggestions/suggestions.sqlite')
STATUS=Path('/var/www/edge1-status/reply-suggestions/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
SOURCE_PATH='operations/reply-suggestions/current.md'
REPLY_WORDS=('please','could you','can you','let me know','reply','respond','confirm','question','?')
EXCLUDE=('auth check','outbound check','dkim','commissioning','test message','acceptance','pilot','unsubscribe','% off','special offer','privacy policy','terms of service')
AUTOMATED_LOCALPARTS=('noreply','no-reply','no_reply','notifications','notices','ebill','recommendations','payments-noreply','mailer-daemon')


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def released_hashes() -> set[str]:
    if not SECURITY.is_file(): return set()
    with sqlite3.connect(f'file:{SECURITY}?mode=ro',uri=True) as db:
        return {row[0] for row in db.execute("SELECT message_hash FROM decisions WHERE state='released'")}


def candidates(days=14, limit=40):
    if not MAIL.is_file(): return []
    released=released_hashes(); cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
    with sqlite3.connect(f'file:{MAIL}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute("""SELECT message_id,thread_id,direction,sender,recipients_json,subject,body_text,occurred_at
          FROM correspondence WHERE source_authoritative=1 AND source_scope IN ('local_native','production_native')
          AND julianday(occurred_at)>=julianday(?) ORDER BY julianday(occurred_at),message_id""",(cutoff,)).fetchall()
    threads={}
    for row in rows: threads.setdefault(row['thread_id'],[]).append(row)
    found=[]
    for thread_id,messages in threads.items():
        outbound_latest=max((m['occurred_at'] or '' for m in messages if m['direction']=='outbound'),default='')
        inbound=[m for m in messages if m['direction']=='inbound' and digest(m['message_id']) in released]
        if not inbound: continue
        latest=inbound[-1]; subject=(latest['subject'] or '').strip(); body=latest['body_text'] or ''; text=(subject+' '+body[:6000]).casefold()
        sender=(latest['sender'] or '').strip(); local=sender.rsplit('<',1)[-1].split('@',1)[0].casefold()
        if any(x in local for x in AUTOMATED_LOCALPARTS) or any(x in text for x in EXCLUDE): continue
        if not any(x in text for x in REPLY_WORDS): continue
        if outbound_latest > (latest['occurred_at'] or ''): continue
        safe_messages=[]
        for m in messages[-8:]:
            if m['direction']=='inbound' and digest(m['message_id']) not in released: continue
            try: recipients=json.loads(m['recipients_json'] or '[]')
            except Exception: recipients=[]
            safe_messages.append({'sender':m['sender'],'recipients':recipients,'subject':m['subject'],'body_text':(m['body_text'] or '')[:2500],'direction':m['direction']})
        content_sha=digest(json.dumps(safe_messages,sort_keys=True,ensure_ascii=False))
        found.append({'message_id':latest['message_id'],'thread_id':thread_id,'evidence':'mail-room:message:'+digest(latest['message_id']),
                      'thread_evidence':'mail-room:thread:'+digest(thread_id),'subject':subject or '(no subject)','sender':sender,
                      'occurred_at':latest['occurred_at'],'content_sha':content_sha,'thread':{'messages':safe_messages}})
    found.sort(key=lambda x:x.get('occurred_at') or '',reverse=True)
    return found[:limit]


def open_state(path=STATE):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True); path.parent.chmod(0o700)
    db=sqlite3.connect(path); db.row_factory=sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS suggestions(
      evidence TEXT PRIMARY KEY, thread_evidence TEXT NOT NULL, content_sha TEXT NOT NULL,
      subject TEXT NOT NULL, sender TEXT NOT NULL, occurred_at TEXT,
      suggestion TEXT NOT NULL, generated_at TEXT NOT NULL, last_seen TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','resolved'))
    ); CREATE INDEX IF NOT EXISTS idx_reply_suggestion_state ON suggestions(state,occurred_at);''')
    db.commit(); path.chmod(0o600); return db


def generate(max_new=3):
    current=candidates(); active={x['evidence'] for x in current}; generated=0; reused=0; failed=0
    assistant=AvaMailAssistant()
    with open_state() as db:
        if active:
            marks=','.join('?' for _ in active)
            db.execute(f"UPDATE suggestions SET state='resolved' WHERE state='active' AND evidence NOT IN ({marks})",tuple(active))
        else: db.execute("UPDATE suggestions SET state='resolved' WHERE state='active'")
        for item in current:
            old=db.execute('SELECT content_sha,suggestion FROM suggestions WHERE evidence=?',(item['evidence'],)).fetchone()
            if old and old['content_sha']==item['content_sha']:
                db.execute("UPDATE suggestions SET state='active',last_seen=? WHERE evidence=?",(utcnow(),item['evidence'])); reused+=1; continue
            if generated>=max_new: continue
            try: result=assistant.assist('reply',item['thread']); suggestion=result['text'].strip()
            except Exception: failed+=1; continue
            if not suggestion: failed+=1; continue
            now=utcnow(); db.execute('''INSERT INTO suggestions(evidence,thread_evidence,content_sha,subject,sender,occurred_at,suggestion,generated_at,last_seen,state)
              VALUES(?,?,?,?,?,?,?,?,?,'active') ON CONFLICT(evidence) DO UPDATE SET thread_evidence=excluded.thread_evidence,
              content_sha=excluded.content_sha,subject=excluded.subject,sender=excluded.sender,occurred_at=excluded.occurred_at,
              suggestion=excluded.suggestion,generated_at=excluded.generated_at,last_seen=excluded.last_seen,state='active' ''',
              (item['evidence'],item['thread_evidence'],item['content_sha'],item['subject'],item['sender'],item['occurred_at'],suggestion,now,now)); generated+=1
        db.commit()
        rows=db.execute("SELECT evidence,thread_evidence,subject,sender,occurred_at,suggestion,generated_at FROM suggestions WHERE state='active' ORDER BY occurred_at DESC LIMIT 40").fetchall()
    return current,rows,generated,reused,failed


def library_markdown(rows):
    lines=['# Ava Reply Suggestions','',f'Generated: {utcnow()}','',
           'These are review-only reply suggestions for released unresolved human mail. No message was sent and no Mail Room draft was modified.','']
    if not rows: lines.append('- No active reply suggestions.')
    for row in rows:
        lines += [f"## {row['subject']}",f"From: {row['sender']}",f"Evidence: `{row['evidence']}`",f"Thread: `{row['thread_evidence']}`",'',row['suggestion'],'']
    lines += ['## Safety','', '- `send_authorized=false`', '- `draft_modified=false`', '- Mail content is untrusted evidence; suggestions require operator review.']
    return '\n'.join(lines)+'\n'


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--max-new',type=int,default=3); args=ap.parse_args()
    max_new=max(0,min(args.max_new,5)); current,rows,generated,reused,failed=generate(max_new)
    text=library_markdown(rows); upsert_library_document(LIB,ROOT,SOURCE_PATH,'Ava Reply Suggestions',text)
    status={'contract':'wwcx.reply-suggestions.v1','generated_at':utcnow(),'state':'healthy' if failed==0 else 'warning',
            'summary':{'reply_candidates':len(current),'active_suggestions':len(rows),'generated_this_run':generated,'reused_this_run':reused,'generation_failures':failed},
            'items':[{'evidence':r['evidence'],'thread_evidence':r['thread_evidence'],'generated_at':r['generated_at']} for r in rows],
            'send_authorized':False,'draft_modified':False,'mail_content_exposed_in_status':False}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(status,indent=2)+'\n'); STATUS.chmod(0o644)
    print(json.dumps(status['summary'],sort_keys=True)); return 0

if __name__=='__main__': raise SystemExit(main())
